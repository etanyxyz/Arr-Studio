"""Regression tests for the ArrEntity base class (plan §8.9)."""

from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.arr_studio.const import (
    CONF_KIND,
    CONF_URL,
    KIND_SONARR,
)
from custom_components.arr_studio.entity import ArrEntity
from custom_components.arr_studio.models import ServerSnapshot


def _snapshot(version: str | None = "4.0.20") -> ServerSnapshot:
    """Return a minimal snapshot for entity tests."""
    return ServerSnapshot(
        entry_id="entry-1",
        kind=KIND_SONARR,
        name="Sonarr",
        version=version,
        online=True,
        error=None,
        library=(),
        recent=(),
        queue=(),
        activity=(),
        disk=None,
        counts={},
    )


def _entity(snapshot: ServerSnapshot | None) -> ArrEntity:
    """Build an ArrEntity backed by a stub coordinator and config entry."""
    coordinator = MagicMock()
    entry = MagicMock()
    entry.entry_id = "entry-1"
    entry.title = "Sonarr"
    entry.data = {CONF_KIND: KIND_SONARR, CONF_URL: "http://sonarr.example"}
    coordinator.config_entry = entry
    coordinator.data = snapshot
    return ArrEntity(coordinator, "queue")


def test_device_info_uses_snapshot_version() -> None:
    """device_info must read the current snapshot (regression for the
    unbound _snapshot method, which raised AttributeError: 'function' object
    has no attribute 'version' on HA 2026.11)."""
    info = _entity(_snapshot()).device_info
    assert info["sw_version"] == "4.0.20"
    assert info["model"] == "Sonarr 4.0.20"
    assert info["configuration_url"] == "http://sonarr.example"


def test_device_info_before_first_refresh() -> None:
    """device_info works before the first successful coordinator refresh."""
    info = _entity(None).device_info
    assert info["sw_version"] is None
    assert info["model"] == "Sonarr"
