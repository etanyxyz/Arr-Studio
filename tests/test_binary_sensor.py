"""Regression tests for the ArrOnlineBinarySensor platform (plan §8.11, §14)."""

from __future__ import annotations

from unittest.mock import MagicMock

from custom_components.arr_studio.binary_sensor import ArrOnlineBinarySensor
from custom_components.arr_studio.const import KIND_SONARR
from custom_components.arr_studio.models import ServerSnapshot


def _snapshot() -> ServerSnapshot:
    """Return a minimal snapshot for entity tests."""
    return ServerSnapshot(
        entry_id="entry-1",
        kind=KIND_SONARR,
        name="Sonarr",
        version="4.0.20",
        online=True,
        error=None,
        library=(),
        recent=(),
        queue=(),
        activity=(),
        disk=None,
        counts={},
    )


def _sensor(snapshot: ServerSnapshot | None) -> ArrOnlineBinarySensor:
    """Build the online sensor backed by a stub coordinator and config entry."""
    coordinator = MagicMock()
    entry = MagicMock()
    entry.entry_id = "entry-1"
    coordinator.config_entry = entry
    coordinator.data = snapshot
    coordinator.last_update_success = True
    coordinator.last_exception = None
    return ArrOnlineBinarySensor(coordinator)


def test_online_sensor_on_after_success() -> None:
    """Online sensor reports on while the last refresh succeeded."""
    sensor = _sensor(_snapshot())
    assert sensor.available is True
    assert sensor.is_on is True
    assert sensor.extra_state_attributes["error"] is None


def test_offline_server_sensor_off_but_available() -> None:
    """Plan §14: server offline -> online sensor off (not unavailable), with
    the last error surfaced in attributes."""
    sensor = _sensor(_snapshot())
    sensor.coordinator.last_update_success = False
    sensor.coordinator.last_exception = Exception("Cannot connect: Connection refused")
    assert sensor.available is True
    assert sensor.is_on is False
    assert sensor.extra_state_attributes["error"] == "Cannot connect: Connection refused"


def test_recovered_server_sensor_on_again() -> None:
    """After recovery the sensor flips back to on without a restart."""
    sensor = _sensor(_snapshot())
    sensor.coordinator.last_update_success = False
    sensor.coordinator.last_exception = Exception("boom")
    assert sensor.is_on is False
    sensor.coordinator.last_update_success = True
    assert sensor.is_on is True


def test_unavailable_before_first_refresh() -> None:
    """Before the first successful refresh there is nothing to report."""
    sensor = _sensor(None)
    assert sensor.available is False
    assert sensor.extra_state_attributes == {}
