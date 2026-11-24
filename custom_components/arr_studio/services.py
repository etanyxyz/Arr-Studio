"""Arr Studio services (plan §8.17)."""

from __future__ import annotations

import logging

import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from custom_components.arr_studio.const import DOMAIN, SERVICE_REFRESH

_LOGGER = logging.getLogger(__name__)

REFRESH_SCHEMA = vol.Schema({vol.Optional("entry_id"): cv.string})


async def async_register_services(hass: HomeAssistant) -> None:
    """Register the arr_studio.refresh service (once)."""
    if hass.services.has_service(DOMAIN, SERVICE_REFRESH):
        return
    hass.services.async_register(
        DOMAIN, SERVICE_REFRESH, _async_refresh, schema=REFRESH_SCHEMA
    )


async def _async_refresh(hass: HomeAssistant, call: ServiceCall) -> None:
    """Refresh one entry by entry_id, or all entries when omitted."""
    entry_id = call.data.get("entry_id")
    entries = hass.config_entries.async_entries(DOMAIN)
    if entry_id is not None:
        entries = [entry for entry in entries if entry.entry_id == entry_id]
    for entry in entries:
        runtime = getattr(entry, "runtime_data", None)
        if runtime is None:
            continue
        _LOGGER.debug("Arr Studio refresh requested for entry %s", entry.entry_id)
        await runtime.coordinator.async_force_refresh()
