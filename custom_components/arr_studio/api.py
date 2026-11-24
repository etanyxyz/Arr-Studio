"""Arr API client — authenticated HTTP calls to Sonarr/Radarr."""

from __future__ import annotations

import asyncio
import inspect
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import aiohttp

from custom_components.arr_studio.const import (
    ALLOWED_VARIANTS,
    API_PATH,
    KIND_RADARR,
    REQUEST_TIMEOUT,
)

_LOGGER = logging.getLogger(__name__)


class ArrError(Exception):
    """Base class for all Arr errors."""


class ArrAuthError(ArrError):
    """401/403 — authentication failed."""


class ArrConnectionError(ArrError):
    """Network-level failure (connection timeout, refused connection, etc.)."""


class ArrResponseError(ArrError):
    """HTTP response with status >= 400 but not auth/not-found."""


class ArrNotFoundError(ArrError):
    """HTTP 404 — the resource was not found."""


def normalize_base_url(value: str) -> str:
    """Strip whitespace, trailing slash and any /api or /api/v3 suffix."""
    url = value.strip().rstrip("/")
    for suffix in ("/api/v3", "/api"):
        if url.endswith(suffix):
            url = url[: -len(suffix)].rstrip("/")
    return url


def normalize_api_key(value: str) -> str:
    """Strip whitespace and newlines from an API key."""
    return value.strip().replace("\n", "").replace("\r", "")


class ArrClient:
    """Authenticated HTTP client for Sonarr/Radarr.

    The API key is confined to this module (plan rule 5). Error messages
    carry the status and path only — never the key or the response body.
    """

    # Also reachable via the class (tests call ArrClient.normalize_base_url(...)).
    normalize_base_url = staticmethod(normalize_base_url)
    normalize_api_key = staticmethod(normalize_api_key)

    def __init__(self, hass, base_url: str, api_key: str, kind: str, verify_ssl: bool = True) -> None:
        self._hass = hass
        self._base_url = normalize_base_url(base_url)
        self._api_key = normalize_api_key(api_key)
        self._kind = kind
        self._verify_ssl = verify_ssl
        self._session: aiohttp.ClientSession | None = None

    @property
    def kind(self) -> str:
        """Server kind ('sonarr' or 'radarr')."""
        return self._kind

    @property
    def base_url(self) -> str:
        """Normalized base URL of the server."""
        return self._base_url

    # -----------------------------------------------------------------------
    # Session / headers
    # -----------------------------------------------------------------------

    async def _async_session(self) -> aiohttp.ClientSession:
        """Lazily obtain the HA-managed session (HA import kept out of module top).

        ``async_get_clientsession`` is a coroutine on older HA releases and a
        plain (sync) function returning the cached session on newer ones;
        handle both so the integration works across versions.
        """
        if self._session is None:
            from homeassistant.helpers.aiohttp_client import async_get_clientsession

            session = async_get_clientsession(self._hass, verify_ssl=self._verify_ssl)
            if inspect.isawaitable(session):
                session = await session
            self._session = session
        return self._session

    def _headers(self) -> dict[str, str]:
        return {"X-Api-Key": self._api_key, "Accept": "application/json"}

    def _cover_headers(self) -> dict[str, str]:
        return {"X-Api-Key": self._api_key, "Accept": "image/*, */*"}

    # -----------------------------------------------------------------------
    # Core request
    # -----------------------------------------------------------------------

    @staticmethod
    def _raise_for_status(resp: aiohttp.ClientResponse, path: str) -> None:
        status = resp.status
        if status in (401, 403):
            raise ArrAuthError(f"Authentication failed ({status}) at {path}")
        if status == 404:
            raise ArrNotFoundError(f"Not found (404) at {path}")
        if status >= 400:
            raise ArrResponseError(f"Status {status} for {path}")

    async def _get_json(self, path: str, params: dict[str, str] | None = None) -> Any:
        """GET {base}/api/v3{path} and decode the JSON body."""
        url = f"{self._base_url}{API_PATH}{path}"
        _LOGGER.debug("Arr %s request: %s", self._kind, path)
        session = await self._async_session()
        try:
            resp = await session.get(
                url,
                headers=self._headers(),
                params=params,
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
            )
        except (aiohttp.ClientError, TimeoutError, asyncio.TimeoutError) as err:
            raise ArrConnectionError(f"Connection to {self._kind} failed at {path}") from err
        try:
            self._raise_for_status(resp, path)
            return await resp.json()
        finally:
            resp.close()

    @staticmethod
    def _records(data: Any) -> list[dict]:
        """Return the list portion of a PagingResource or bare-array payload."""
        if isinstance(data, dict) and isinstance(data.get("records"), list):
            return data["records"]
        if isinstance(data, list):
            return data
        return []

    def _include_params(self, page_size: int, sort_key: str, sort_direction: str) -> dict[str, str]:
        params: dict[str, str] = {
            "page": "1",
            "pageSize": str(page_size),
            "sortKey": sort_key,
            "sortDirection": sort_direction,
        }
        if self._kind == KIND_RADARR:
            params["includeMovie"] = "true"
        else:
            params["includeSeries"] = "true"
            params["includeEpisode"] = "true"
        return params

    # -----------------------------------------------------------------------
    # Public async methods
    # -----------------------------------------------------------------------

    async def async_get_status(self) -> dict:
        """GET /system/status. Returns the status dict."""
        data = await self._get_json("/system/status")
        return data if isinstance(data, dict) else {}

    async def async_get_health(self) -> list[dict]:
        """GET /health. Returns the health list."""
        return self._records(await self._get_json("/health"))

    async def async_get_diskspace(self) -> list[dict]:
        """GET /diskspace. Returns the disk list."""
        return self._records(await self._get_json("/diskspace"))

    async def async_get_queue(self, page_size: int = 100) -> list[dict]:
        """GET /queue. Returns queue records."""
        return self._records(await self._get_json("/queue", self._include_params(page_size, "timeleft", "ascending")))

    async def async_get_history(self, page_size: int = 20) -> list[dict]:
        """GET /history. Returns history records."""
        return self._records(await self._get_json("/history", self._include_params(page_size, "date", "descending")))

    async def async_get_library(self) -> list[dict]:
        """GET /series (sonarr) or /movie (radarr). Returns the bare array."""
        path = "/movie" if self._kind == KIND_RADARR else "/series"
        return self._records(await self._get_json(path))

    async def async_get_calendar(self, days: int = 14) -> list[dict]:
        """GET /calendar from today for `days` days. Returns the list."""
        now = datetime.now(timezone.utc)
        params: dict[str, str] = {
            "start": now.strftime("%Y-%m-%d"),
            "end": (now + timedelta(days=days)).strftime("%Y-%m-%d"),
        }
        if self._kind == KIND_RADARR:
            params["includeMovie"] = "true"
        else:
            params["includeSeries"] = "true"
        return self._records(await self._get_json("/calendar", params))

    async def async_get_cover(self, media_id: int, variant: str = "poster") -> tuple[bytes, str] | None:
        """GET /mediacover/{id}/{variant}.jpg. Returns (body, content_type) or None on 404."""
        variant = variant.lower()
        if variant not in ALLOWED_VARIANTS:
            raise ValueError(f"variant must be one of {ALLOWED_VARIANTS}")
        path = f"/mediacover/{media_id}/{variant}.jpg"
        url = f"{self._base_url}{API_PATH}{path}"
        _LOGGER.debug("Arr %s cover request: %s", self._kind, path)
        session = await self._async_session()
        try:
            resp = await session.get(
                url,
                headers=self._cover_headers(),
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
            )
        except (aiohttp.ClientError, TimeoutError, asyncio.TimeoutError) as err:
            raise ArrConnectionError(f"Connection to {self._kind} failed at {path}") from err
        try:
            if resp.status == 404:
                return None
            self._raise_for_status(resp, path)
            content_type = resp.headers.get("Content-Type", "")
            return await resp.read(), content_type
        finally:
            resp.close()

    async def async_validate(self) -> dict:
        """Fetch status; raise ArrResponseError when appName != kind. Returns status."""
        status = await self.async_get_status()
        app_name = status.get("appName", "")
        if app_name.lower() != self._kind:
            raise ArrResponseError(f"Expected {self._kind}, got {app_name}")
        return status

    # -----------------------------------------------------------------------
    # Cleanup
    # -----------------------------------------------------------------------

    async def close(self) -> None:
        """Drop our session reference; close it when it is ours to close."""
        session, self._session = self._session, None
        if session is not None:
            result = session.close()
            if inspect.isawaitable(result):
                await result
