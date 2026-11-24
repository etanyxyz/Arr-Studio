"""Arr Studio coordinator - per-entry data update (plan §8.7)."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from custom_components.arr_studio.api import (
    ArrAuthError,
    ArrClient,
    ArrConnectionError,
    ArrResponseError,
)
from custom_components.arr_studio.const import KIND_LABELS, KIND_SONARR
from custom_components.arr_studio.models import MediaItem, ServerSnapshot
from custom_components.arr_studio.normalize import (
    compute_missing,
    normalize_disks,
    normalize_health,
    normalize_history,
    normalize_movie,
    normalize_queue,
    normalize_series,
    sort_newest_first,
)

_LOGGER = logging.getLogger(__name__)

STATUS_CACHE_TTL = timedelta(seconds=3600)
SPEED_MAX_DT = 300.0
SPEED_SMOOTHING = 0.7
CALENDAR_DAYS = 14


@dataclass
class ArrRuntimeData:
    """Client and coordinator attached to a config entry (entry.runtime_data)."""

    client: ArrClient
    coordinator: ArrCoordinator


class ArrCoordinator(DataUpdateCoordinator[ServerSnapshot]):
    """Poll one Sonarr/Radarr server and produce a ServerSnapshot."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        client: ArrClient,
        scan_interval: int,
        recent_limit: int,
        library_refresh_minutes: int,
        show_unmonitored: bool,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"Arr Studio {client.kind.title()}",
            update_interval=timedelta(seconds=scan_interval),
            always_update=False,
        )
        self._client = client
        self._recent_limit = recent_limit
        self._library_refresh_minutes = library_refresh_minutes
        self._show_unmonitored = show_unmonitored
        self._status: dict[str, Any] | None = None
        self._status_at: datetime | None = None
        self._library_raw: list[dict] = []
        self._library: tuple[MediaItem, ...] = ()
        self._calendar: tuple[dict, ...] = ()
        self._library_due: datetime | None = None
        self._speed_state: dict[str, tuple[float, float]] = {}
        self._last_queue_at: datetime | None = None

    @property
    def client(self) -> ArrClient:
        """The underlying API client."""
        return self._client

    @property
    def base_url(self) -> str:
        """Normalized base URL of the server."""
        return self._client.base_url

    @property
    def show_unmonitored(self) -> bool:
        """Whether unmonitored items count as missing."""
        return self._show_unmonitored

    def cover(self, media_id: int, variant: str) -> Any:
        """Delegate a cover fetch to the client (awaited by the HTTP view)."""
        return self._client.async_get_cover(media_id, variant)

    async def async_force_refresh(self) -> None:
        """Force an immediate refresh of the data."""
        await self.async_request_refresh()

    # ------------------------------------------------------------------
    # Polling
    # ------------------------------------------------------------------

    async def _async_status(self) -> dict[str, Any] | None:
        """Return the status, cached for 3600 s.

        On failure reuse the cache; without a cache return None.
        Auth failures always abort the refresh (reauth).
        """
        now = datetime.now(timezone.utc)
        if (
            self._status is not None
            and self._status_at is not None
            and now - self._status_at < STATUS_CACHE_TTL
        ):
            return self._status
        try:
            status = await self._client.async_validate()
        except ArrAuthError:
            raise ConfigEntryAuthFailed from None
        except (ArrConnectionError, ArrResponseError) as err:
            if self._status is not None:
                _LOGGER.warning("Arr Studio status refresh failed; using cached status: %s", err)
                return self._status
            _LOGGER.warning("Arr Studio status unavailable: %s", err)
            return None
        self._status = status
        self._status_at = now
        return status

    @staticmethod
    def _raise_for_arr_error(result: Any) -> None:
        """Map Arr client errors onto coordinator errors (plan §8.7 step 8)."""
        if not isinstance(result, BaseException):
            return
        if isinstance(result, ArrAuthError):
            raise ConfigEntryAuthFailed from result
        if isinstance(result, (ArrConnectionError, ArrResponseError)):
            raise UpdateFailed(str(result)) from result
        raise result

    def _media_items_from_library(self, library_raw: list[Any]) -> tuple[MediaItem, ...]:
        """Build MediaItems from the raw library list, newest first."""
        entry_id = self.config_entry.entry_id
        kind = self._client.kind
        base_url = self.base_url
        items: list[MediaItem] = []
        for raw in library_raw:
            if not isinstance(raw, dict):
                continue
            if kind == KIND_SONARR:
                items.append(normalize_series(entry_id, raw, base_url))
            else:
                items.append(normalize_movie(entry_id, raw, base_url))
        return sort_newest_first(items)

    async def _async_refresh_library(self, now: datetime) -> None:
        """Refresh library and calendar when due; keep the cache on failure."""
        library_raw, calendar_raw = await asyncio.gather(
            self._client.async_get_library(),
            self._client.async_get_calendar(days=CALENDAR_DAYS),
            return_exceptions=True,
        )
        for result in (library_raw, calendar_raw):
            if isinstance(result, ArrAuthError):
                raise ConfigEntryAuthFailed from result
        if not isinstance(library_raw, BaseException):
            self._library_raw = [raw for raw in library_raw if isinstance(raw, dict)]
            self._library = self._media_items_from_library(self._library_raw)
        if not isinstance(calendar_raw, BaseException):
            self._calendar = tuple(raw for raw in calendar_raw if isinstance(raw, dict))
        if isinstance(library_raw, BaseException) or isinstance(calendar_raw, BaseException):
            _LOGGER.warning("Arr Studio library refresh failed; keeping previous cache")
        self._library_due = now + timedelta(minutes=self._library_refresh_minutes)

    def _update_speed_state(self, queue_raw: list[dict], now: datetime) -> int:
        """Smooth per-download speed from size-left deltas; return the total."""
        dt = (now - self._last_queue_at).total_seconds() if self._last_queue_at else 0.0
        previous = self._speed_state
        self._speed_state = {}
        if not queue_raw or dt > SPEED_MAX_DT:
            self._last_queue_at = now
            return 0
        total = 0.0
        for raw in queue_raw:
            download_id = str(raw.get("downloadId", raw.get("id")))
            size_left = raw.get("sizeleft", 0) or 0
            prev = previous.get(download_id)
            if prev is None or dt <= 0:
                speed = 0.0
            else:
                prev_speed, prev_size_left = prev
                delta_bytes = max(0, prev_size_left - size_left)
                speed = SPEED_SMOOTHING * prev_speed + (1 - SPEED_SMOOTHING) * (delta_bytes / dt)
            self._speed_state[download_id] = (speed, size_left)
            total += speed
        self._last_queue_at = now
        return int(total)

    async def _async_update_data(self) -> ServerSnapshot:
        """Fetch fresh data for this server and build the snapshot."""
        now = datetime.now(timezone.utc)
        entry_id = self.config_entry.entry_id
        kind = self._client.kind

        # 1. Status (cached 3600 s).
        status = await self._async_status()

        # 2. Per-poll calls.
        health_raw, disks_raw, queue_raw, history_raw = await asyncio.gather(
            self._client.async_get_health(),
            self._client.async_get_diskspace(),
            self._client.async_get_queue(),
            self._client.async_get_history(),
            return_exceptions=True,
        )
        for result in (health_raw, disks_raw, queue_raw, history_raw):
            self._raise_for_arr_error(result)

        # 3. Library and calendar when due.
        if self._library_due is None or now >= self._library_due:
            await self._async_refresh_library(now)

        # 4. Recent from the newest library items.
        library = self._library
        recent = library[: self._recent_limit]

        # 5. Queue items and smoothed download speed.
        queue_items = tuple(
            normalize_queue(entry_id, kind, raw, self.base_url)
            for raw in queue_raw
            if isinstance(raw, dict)
        )
        speed_bps = self._update_speed_state(
            [raw for raw in queue_raw if isinstance(raw, dict)], now
        )

        # 6. Counts and remaining payloads.
        health = normalize_health(health_raw)
        activity = tuple(
            item
            for item in (
                normalize_history(entry_id, kind, raw, self.base_url)
                for raw in history_raw
                if isinstance(raw, dict)
            )
            if item is not None
        )
        disks = normalize_disks(disks_raw)
        disk = max(disks, key=lambda d: d.total) if disks else None
        counts = {
            "library": len(library),
            "queue": len(queue_items),
            "downloading": sum(1 for item in queue_items if item.status == "downloading"),
            "recent": len(recent),
            "missing": compute_missing(kind, self._library_raw, self._show_unmonitored),
            "upcoming": len(self._calendar),
            "health": len(health),
        }

        # 7. Snapshot.
        return ServerSnapshot(
            entry_id=entry_id,
            kind=kind,
            name=(status or {}).get("instanceName") or KIND_LABELS.get(kind, "Arr"),
            version=(status or {}).get("version") or None,
            online=True,
            error=None,
            library=library,
            recent=tuple(recent),
            queue=queue_items,
            activity=activity,
            disk=disk,
            counts=counts,
            health=health,
            speed_bps=speed_bps,
            updated_at=now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        )
