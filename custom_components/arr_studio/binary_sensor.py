"""Binary sensor platform for Arr Studio (plan §8.11)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from custom_components.arr_studio.coordinator import ArrCoordinator, ArrRuntimeData
from custom_components.arr_studio.entity import ArrEntity


class ArrOnlineBinarySensor(ArrEntity, BinarySensorEntity):
    """Online/offline state of one configured server."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator: ArrCoordinator) -> None:
        super().__init__(coordinator, "online")
        self._attr_name = "Online"

    @property
    def is_on(self) -> bool | None:
        """True while the last refresh succeeded."""
        snapshot = self._snapshot()
        if snapshot is None:
            return None
        return snapshot.online

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Last update timestamp and any short error text."""
        snapshot = self._snapshot()
        if snapshot is None:
            return {}
        return {"last_update": snapshot.updated_at, "error": snapshot.error}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the online binary sensor for one server."""
    runtime: ArrRuntimeData = entry.runtime_data
    async_add_entities([ArrOnlineBinarySensor(runtime.coordinator)])
