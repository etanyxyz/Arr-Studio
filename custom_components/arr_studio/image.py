"""Image platform for Arr Studio (plan §8.12)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from homeassistant.components.image import ImageEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from custom_components.arr_studio.api import ArrError
from custom_components.arr_studio.coordinator import ArrCoordinator, ArrRuntimeData
from custom_components.arr_studio.entity import ArrEntity
from custom_components.arr_studio.normalize import parse_datetime

PLACEHOLDER_PATH = Path(__file__).parent / "frontend" / "placeholder.svg"


class ArrLatestPosterImage(ArrEntity, ImageEntity):
    """Latest recent item poster for one server, with a bundled fallback."""

    _attr_content_type = "image/jpeg"

    def __init__(self, coordinator: ArrCoordinator) -> None:
        super().__init__(coordinator, "latest_poster")
        self._attr_name = "Latest poster"

    async def async_added_to_hass(self) -> None:
        """Initialize the image part now that the platform has set hass.

        The CoordinatorEntity MRO chain stops before ImageEntity.__init__,
        so access_tokens (read by the image view and state attributes) is
        initialized here instead.
        """
        if not hasattr(self, "access_tokens"):
            ImageEntity.__init__(self, self.hass)
        await super().async_added_to_hass()

    def _latest_item(self) -> Any | None:
        """Newest recent item, or None before the first refresh."""
        snapshot = self._snapshot()
        if snapshot is None or not snapshot.recent:
            return None
        return snapshot.recent[0]

    @property
    def image_last_updated(self) -> datetime | None:
        """When the underlying snapshot was last updated."""
        snapshot = self._snapshot()
        if snapshot is None or not snapshot.updated_at:
            return None
        return parse_datetime(snapshot.updated_at)

    async def _async_placeholder(self) -> tuple[bytes, str] | None:
        """Bundled placeholder image, or None when it is unavailable."""
        try:
            data = await self.hass.async_add_executor_job(PLACEHOLDER_PATH.read_bytes)
        except OSError:
            return None
        return data, "image/svg+xml"

    async def async_image(self) -> bytes | None:
        """Latest poster bytes; never raises (falls back to the placeholder)."""
        item = self._latest_item()
        if item is not None:
            try:
                result = await self.coordinator.client.async_get_cover(item.id, "poster")
            except ArrError:
                result = None
            if result is not None:
                self._attr_content_type = result[1]
                return result[0]
        placeholder = await self._async_placeholder()
        if placeholder is None:
            return None
        self._attr_content_type = placeholder[1]
        return placeholder[0]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Title, kind and item id of the latest recent item (scalars only)."""
        item = self._latest_item()
        return {
            "title": item.title if item is not None else None,
            "kind": item.kind if item is not None else None,
            "item_id": item.id if item is not None else None,
        }


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the latest-poster image for one server."""
    runtime: ArrRuntimeData = entry.runtime_data
    async_add_entities([ArrLatestPosterImage(runtime.coordinator)])
