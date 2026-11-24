"""Frontend panel registration for Arr Studio (plan §8.16)."""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.components import frontend
from homeassistant.components.frontend import async_register_built_in_panel
from homeassistant.components.http import StaticPathConfig
from homeassistant.core import HomeAssistant
from homeassistant.loader import async_get_integration

from custom_components.arr_studio.const import (
    DATA_FRONTEND_REGISTERED,
    DOMAIN,
    FRONTEND_ENTRY,
    FRONTEND_STATIC_URL,
    PANEL_ELEMENT,
    PANEL_ICON,
    PANEL_TITLE,
    PANEL_URL_PATH,
)

_LOGGER = logging.getLogger(__name__)


async def _async_version(hass: HomeAssistant) -> str:
    """Integration version for the module_url cache-buster."""
    integration = await async_get_integration(hass, DOMAIN)
    return integration.version


async def async_register_frontend(hass: HomeAssistant) -> None:
    """Register the static files and the sidebar panel (idempotent)."""
    if hass.data.get(DATA_FRONTEND_REGISTERED):
        return
    if "frontend" not in hass.config.components:
        _LOGGER.warning("Frontend component not loaded; skipping Arr Studio panel")
        return

    files = Path(__file__).parent / "frontend"
    await hass.http.async_register_static_paths(
        [StaticPathConfig(FRONTEND_STATIC_URL, str(files), True)]
    )
    version = await _async_version(hass)
    try:
        async_register_built_in_panel(
            hass,
            component_name="custom",
            sidebar_title=PANEL_TITLE,
            sidebar_icon=PANEL_ICON,
            frontend_url_path=PANEL_URL_PATH,
            require_admin=False,
            config={
                "_panel_custom": {
                    "name": PANEL_ELEMENT,
                    "module_url": f"{FRONTEND_STATIC_URL}/{FRONTEND_ENTRY}?v={version}",
                    "embed_iframe": False,
                    "trust_external": False,
                }
            },
        )
    except (ValueError, RuntimeError) as err:
        _LOGGER.debug("Arr Studio panel already registered: %s", err)
    hass.data[DATA_FRONTEND_REGISTERED] = True


def async_remove_panel(hass: HomeAssistant) -> None:
    """Remove the sidebar panel (called when the last entry unloads)."""
    frontend.async_remove_panel(hass, PANEL_URL_PATH)
