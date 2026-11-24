"""Button platform for Arr Studio (plan §8.13)."""

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from custom_components.arr_studio.coordinator import ArrCoordinator, ArrRuntimeData
from custom_components.arr_studio.entity import ArrEntity


class ArrRefreshButton(ArrEntity, ButtonEntity):
    """Force an immediate refresh of the server data."""

    _attr_icon = "mdi:refresh"

    def __init__(self, coordinator: ArrCoordinator) -> None:
        super().__init__(coordinator, "refresh")
        self._attr_name = "Refresh"

    async def async_press(self) -> None:
        """Request a coordinator refresh."""
        await self.coordinator.async_request_refresh()


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the refresh button for one server."""
    runtime: ArrRuntimeData = entry.runtime_data
    async_add_entities([ArrRefreshButton(runtime.coordinator)])
