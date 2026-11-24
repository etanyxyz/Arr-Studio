"""Base entity for Arr Studio platforms (plan §8.9)."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from custom_components.arr_studio.const import CONF_KIND, CONF_URL, DOMAIN, KIND_LABELS
from custom_components.arr_studio.coordinator import ArrCoordinator
from custom_components.arr_studio.models import ServerSnapshot


class ArrEntity(CoordinatorEntity[ArrCoordinator]):
    """Base class for all Arr Studio entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: ArrCoordinator, key: str) -> None:
        """Initialize via CoordinatorEntity; unique id is {entry_id}_{key}."""
        super().__init__(coordinator)
        self._key = key
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.entry_id}_{key}"

    @property
    def device_info(self) -> DeviceInfo:
        """Device registry info: one service device per configured server."""
        entry = self.coordinator.config_entry
        snapshot = self._snapshot()
        version = snapshot.version if snapshot is not None else None
        label = KIND_LABELS.get(entry.data.get(CONF_KIND), "Arr")
        return {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": entry.title,
            "manufacturer": label,
            "model": f"{label} {version or ''}".strip(),
            "sw_version": version,
            "configuration_url": entry.data.get(CONF_URL),
            "entry_type": DeviceEntryType.SERVICE,
        }

    @property
    def available(self) -> bool:
        """Available while the coordinator's last update succeeded."""
        return self.coordinator.last_update_success

    def _snapshot(self) -> ServerSnapshot | None:
        """Current snapshot (None before the first successful refresh)."""
        return self.coordinator.data
