"""Diagnostics for Arr Studio (plan §8.18)."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from custom_components.arr_studio.const import CONF_API_KEY
from custom_components.arr_studio.models import ServerSnapshot

REDACTED = "**REDACTED**"
QUEUE_TITLE_LIMIT = 10


def _snapshot_summary(snapshot: ServerSnapshot) -> dict[str, Any]:
    """Small, safe summary of the current snapshot."""
    return {
        "kind": snapshot.kind,
        "online": snapshot.online,
        "counts": dict(snapshot.counts),
        "version": snapshot.version,
        "queue_titles": [item.title for item in snapshot.queue][:QUEUE_TITLE_LIMIT],
    }


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: ConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a single config entry without any key fragments."""
    snapshot: ServerSnapshot | None = None
    runtime = getattr(entry, "runtime_data", None)
    if runtime is not None:
        snapshot = runtime.coordinator.data
    return {
        "entry": {
            "title": entry.title,
            "data": {**entry.data, CONF_API_KEY: REDACTED},
            "options": dict(entry.options),
        },
        "snapshot": _snapshot_summary(snapshot) if snapshot is not None else None,
    }
