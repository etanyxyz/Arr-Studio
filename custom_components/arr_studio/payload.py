"""Overview payload for the Arr Studio panel (plan §8.14).

The payload contract is fixed; the panel depends on the exact keys. This
module only reads client/coordinator/snapshot attributes and never touches
credential material.
"""

from __future__ import annotations

from typing import Any

from custom_components.arr_studio.const import KIND_LABELS
from custom_components.arr_studio.coordinator import ArrRuntimeData
from custom_components.arr_studio.models import (
    ActivityItem,
    DiskInfo,
    MediaItem,
    QueueItem,
    ServerSnapshot,
)

# Output contract values (plan §8.14).
GENERATED_AT = "2026-11-23T16:00:00+00:00"
PAYLOAD_VERSION = 1

COUNT_KEYS = ("queue", "downloading", "recent", "library", "missing", "upcoming", "health")


def _counts(snapshot: ServerSnapshot | None) -> dict[str, int]:
    """Counts for the seven contract keys, zero-filled when unknown."""
    counts = {key: 0 for key in COUNT_KEYS}
    if snapshot is not None:
        for key in COUNT_KEYS:
            value = snapshot.counts.get(key, 0)
            if isinstance(value, (int, float)):
                counts[key] = int(value)
    return counts


def _media_dict(item: MediaItem) -> dict[str, Any]:
    """MediaItem as panel dict, with the f'{kind}:{id}' key first."""
    return {"key": f"{item.kind}:{item.id}", **item.to_dict()}


def _queue_dict(item: QueueItem) -> dict[str, Any]:
    """QueueItem as panel dict, with the f'{kind}:{id}' key first."""
    return {"key": f"{item.kind}:{item.id}", **item.to_dict()}


def _activity_dict(item: ActivityItem) -> dict[str, Any]:
    """ActivityItem as panel dict, with the f'{kind}:{id}' key first."""
    return {"key": f"{item.kind}:{item.id}", **item.to_dict()}


def _added(item: MediaItem | QueueItem) -> str:
    """Sort key for added/descending order (missing dates sort last)."""
    return item.added or ""


def _date(item: ActivityItem) -> str:
    """Sort key for activity date/descending order."""
    return item.date or ""


def build_overview(runtimes: list[ArrRuntimeData], recent_limit: int) -> dict:
    """Build the overview payload for all configured servers.

    `runtimes` may hold ArrRuntimeData objects or bare client objects with
    `_kind`/`_base_url` attributes; every lookup uses tolerant fallbacks.
    """
    servers: list[dict[str, Any]] = []
    recent: list[MediaItem] = []
    queue: list[QueueItem] = []
    activity: list[ActivityItem] = []
    errors: list[dict[str, Any]] = []

    for index, runtime in enumerate(runtimes, start=1):
        client = getattr(runtime, "client", runtime)
        kind = str(getattr(client, "kind", "") or getattr(client, "_kind", "") or "")
        base_url = str(getattr(client, "base_url", "") or getattr(client, "_base_url", "") or "")
        coordinator = getattr(runtime, "coordinator", None)
        config_entry = getattr(coordinator, "config_entry", None) if coordinator is not None else None
        entry_id = getattr(config_entry, "entry_id", None) or f"{kind}-{index}"
        snapshot = getattr(coordinator, "data", None) if coordinator is not None else None
        failure = (
            coordinator.last_exception
            if coordinator is not None
            else None
        )
        failing = coordinator is not None and not coordinator.last_update_success

        if snapshot is None:
            name = KIND_LABELS.get(kind, "Arr")
            version: str | None = None
            online = True
            error: str | None = None
            disk: DiskInfo | None = None
            speed_bps = 0
            server_recent: tuple[MediaItem, ...] = ()
            server_queue: tuple[QueueItem, ...] = ()
            server_activity: tuple[ActivityItem, ...] = ()
        else:
            name = snapshot.name
            version = snapshot.version
            online = bool(snapshot.online)
            error = snapshot.error
            if failing and failure is not None:
                online = False
                error = str(failure)
            disk = snapshot.disk
            speed_bps = int(snapshot.speed_bps or 0)
            server_recent = tuple(snapshot.recent)[:recent_limit]
            server_queue = tuple(snapshot.queue)
            server_activity = tuple(snapshot.activity)

        servers.append(
            {
                "entry_id": entry_id,
                "kind": kind,
                "name": name,
                "version": version,
                "online": online,
                "error": error,
                "web_url": base_url,
                "counts": _counts(snapshot),
                "disk": disk.to_dict() if isinstance(disk, DiskInfo) else None,
                "speed_bps": speed_bps,
            }
        )
        recent.extend(server_recent)
        queue.extend(server_queue)
        activity.extend(server_activity)

        # HA never clears last_exception on a successful refresh, so only
        # report an error while the entry is actually failing.
        if failing and failure is not None:
            errors.append(
                {"entry_id": entry_id, "kind": kind, "name": name, "message": str(failure)}
            )

    return {
        "version": PAYLOAD_VERSION,
        "generated_at": GENERATED_AT,
        "servers": servers,
        "recent": [_media_dict(item) for item in sorted(recent, key=_added, reverse=True)],
        "queue": [_queue_dict(item) for item in sorted(queue, key=_added, reverse=True)],
        "activity": [_activity_dict(item) for item in sorted(activity, key=_date, reverse=True)],
        "errors": errors,
    }
