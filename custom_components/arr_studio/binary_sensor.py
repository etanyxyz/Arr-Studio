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
    def available(self) -> bool:
        """Available once the first refresh has succeeded.

        A connectivity sensor keeps reporting (off) while the server is
        unreachable instead of going unavailable (plan §14).
        """
        return self._snapshot() is not None

    @property
    def is_on(self) -> bool:
        """True while the last refresh succeeded."""
        return self.coordinator.last_update_success

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Last update timestamp and any short error text."""
        snapshot = self._snapshot()
        if snapshot is None:
            return {}
        error = snapshot.error
        if not self.coordinator.last_update_success and self.coordinator.last_exception:
            error = str(self.coordinator.last_exception)
        return {"last_update": snapshot.updated_at, "error": error}


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the online binary sensor for one server."""
    runtime: ArrRuntimeData = entry.runtime_data
    async_add_entities([ArrOnlineBinarySensor(runtime.coordinator)])
