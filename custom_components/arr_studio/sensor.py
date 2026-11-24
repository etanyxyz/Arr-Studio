"""Sensor platform for Arr Studio (plan §8.10)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from custom_components.arr_studio.const import KIND_SONARR
from custom_components.arr_studio.coordinator import ArrCoordinator, ArrRuntimeData
from custom_components.arr_studio.entity import ArrEntity

GIB = 1024**3
MB = 1024 * 1024

SENSOR_KEYS = ("queue", "downloading", "recent", "library", "missing", "disk_free", "health")

SENSOR_META = {
    "queue": ("Queue", "mdi:download-network"),
    "downloading": ("Downloading", "mdi:progress-download"),
    "recent": ("Recent additions", "mdi:new-box"),
    "library": ("Library", "mdi:movie-open"),
    "missing": ("Missing", "mdi:alert-circle-outline"),
    "disk_free": ("Disk free", "mdi:harddisk"),
    "health": ("Health issues", "mdi:stethoscope"),
}


def _worst_health(health: tuple[dict, ...]) -> str:
    """error/warning/ok from the health entry types."""
    types = {item.get("type") for item in health}
    if "error" in types:
        return "error"
    if "warning" in types:
        return "warning"
    return "ok"


class ArrSensor(ArrEntity, SensorEntity):
    """One Arr Studio sensor; a server contributes one entity per key."""

    def __init__(self, coordinator: ArrCoordinator, key: str) -> None:
        super().__init__(coordinator, key)
        name, icon = SENSOR_META[key]
        self._attr_name = name
        self._attr_icon = icon
        if key == "disk_free":
            self._attr_device_class = SensorDeviceClass.DATA_SIZE
            self._attr_native_unit_of_measurement = "GiB"
            self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int | float | None:
        """Counts, or GiB free for disk_free."""
        snapshot = self._snapshot()
        if snapshot is None:
            return None
        if self._key == "disk_free":
            disk = snapshot.disk
            if disk is None:
                return None
            return round(disk.free / GIB, 1)
        return snapshot.counts.get(self._key)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Up to five scalar attributes per key (plan §8.10)."""
        snapshot = self._snapshot()
        if snapshot is None:
            return {}
        counts = snapshot.counts
        if self._key == "queue":
            return {"downloading": counts.get("downloading", 0)}
        if self._key == "downloading":
            return {"speed": round(snapshot.speed_bps / MB, 2)}
        if self._key == "recent":
            latest = snapshot.recent[0] if snapshot.recent else None
            return {
                "latest_title": latest.title if latest is not None else None,
                "latest_added": latest.added if latest is not None else None,
            }
        if self._key == "library":
            label = "shows" if snapshot.kind == KIND_SONARR else "movies"
            size_gb = round(sum(item.size for item in snapshot.library) / GIB, 1)
            return {label: counts.get("library", 0), "size_gb": size_gb}
        if self._key == "missing":
            return {"monitored_only": not self.coordinator.show_unmonitored}
        if self._key == "disk_free":
            disk = snapshot.disk
            if disk is None:
                return {}
            return {
                "path": disk.path,
                "total_gb": round(disk.total / GIB, 1),
                "used_pct": disk.used_pct,
            }
        if self._key == "health":
            return {"worst": _worst_health(snapshot.health)}
        return {}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the seven sensors for one server."""
    runtime: ArrRuntimeData = entry.runtime_data
    async_add_entities(
        ArrSensor(runtime.coordinator, key) for key in SENSOR_KEYS
    )
