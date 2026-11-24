"""Arr Studio custom component (plan §8.17)."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from custom_components.arr_studio.api import ArrClient
from custom_components.arr_studio.config_flow import ArrStudioFlow  # noqa: F401
from custom_components.arr_studio.const import (
    CONF_API_KEY,
    CONF_KIND,
    CONF_LIBRARY_REFRESH,
    CONF_RECENT_LIMIT,
    CONF_SCAN_INTERVAL,
    CONF_SHOW_UNMONITORED,
    CONF_URL,
    CONF_VERIFY_SSL,
    DEFAULT_LIBRARY_REFRESH,
    DEFAULT_RECENT_LIMIT,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SHOW_UNMONITORED,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    PLATFORMS,
)
from custom_components.arr_studio.coordinator import ArrCoordinator, ArrRuntimeData
from custom_components.arr_studio.diagnostics import (  # noqa: F401
    async_get_config_entry_diagnostics,
)
from custom_components.arr_studio.frontend import async_register_frontend, async_remove_panel
from custom_components.arr_studio.http_views import async_register_views
from custom_components.arr_studio.services import async_register_services

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict[str, object]) -> bool:
    """Set up Arr Studio: frontend, views and services."""
    await async_register_frontend(hass)
    async_register_views(hass)
    await async_register_services(hass)
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up an Arr Studio config entry."""
    data = {**entry.data, **entry.options}
    client = ArrClient(
        hass,
        data[CONF_URL],
        data[CONF_API_KEY],
        data[CONF_KIND],
        data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
    )
    coordinator = ArrCoordinator(
        hass,
        entry,
        client,
        int(data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)),
        int(data.get(CONF_RECENT_LIMIT, DEFAULT_RECENT_LIMIT)),
        int(data.get(CONF_LIBRARY_REFRESH, DEFAULT_LIBRARY_REFRESH)),
        bool(data.get(CONF_SHOW_UNMONITORED, DEFAULT_SHOW_UNMONITORED)),
    )
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = ArrRuntimeData(client=client, coordinator=coordinator)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload an Arr Studio config entry."""
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok and not hass.config_entries.async_entries(DOMAIN):
        async_remove_panel(hass)
    return ok


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the entry after its options changed."""
    if await hass.config_entries.async_unload(entry):
        await hass.config_entries.async_reload(entry)
