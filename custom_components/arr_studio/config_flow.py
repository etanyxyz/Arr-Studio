"""Config flow for Arr Studio (plan §8.8)."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.helpers import selector

from custom_components.arr_studio.api import (
    ArrAuthError,
    ArrClient,
    ArrConnectionError,
    ArrResponseError,
    normalize_api_key,
    normalize_base_url,
)
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
    KIND_LABELS,
    KIND_RADARR,
    KIND_SONARR,
)

OPTIONS_DEFAULTS = {
    CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
    CONF_RECENT_LIMIT: DEFAULT_RECENT_LIMIT,
    CONF_LIBRARY_REFRESH: DEFAULT_LIBRARY_REFRESH,
    CONF_SHOW_UNMONITORED: DEFAULT_SHOW_UNMONITORED,
    CONF_VERIFY_SSL: DEFAULT_VERIFY_SSL,
}

USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_KIND, default=KIND_SONARR): selector.SelectSelector(
            {
                "options": [
                    {"value": KIND_SONARR, "label": KIND_LABELS[KIND_SONARR]},
                    {"value": KIND_RADARR, "label": KIND_LABELS[KIND_RADARR]},
                ]
            }
        ),
        vol.Required(CONF_URL): selector.TextSelector({"type": selector.TextSelectorType.URL}),
        vol.Required(CONF_API_KEY): selector.TextSelector({"type": selector.TextSelectorType.PASSWORD}),
        vol.Required(CONF_VERIFY_SSL, default=DEFAULT_VERIFY_SSL): selector.BooleanSelector(),
    }
)

REAUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_API_KEY): selector.TextSelector(
            {"type": selector.TextSelectorType.PASSWORD}
        )
    }
)


class ArrStudioFlow(ConfigFlow, domain=DOMAIN):
    """Handle the Arr Studio config flow."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow for an entry."""
        return ArrStudioOptionsFlow()

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the initial setup step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            kind = user_input[CONF_KIND]
            url = normalize_base_url(str(user_input.get(CONF_URL, "")))
            api_key = normalize_api_key(str(user_input.get(CONF_API_KEY, "")))
            verify_ssl = bool(user_input.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL))
            if not url or not api_key:
                errors["base"] = "invalid_input"
            else:
                client = ArrClient(self.hass, url, api_key, kind, verify_ssl)
                try:
                    status = await client.async_validate()
                except ArrAuthError:
                    errors["base"] = "invalid_auth"
                except ArrResponseError:
                    errors["base"] = "wrong_server"
                except ArrConnectionError:
                    errors["base"] = "cannot_connect"
                else:
                    await self.async_set_unique_id(f"{kind}_{url}", raise_on_progress=False)
                    self._abort_if_unique_id_configured(updates={CONF_API_KEY: api_key})
                    title = status.get("instanceName") or KIND_LABELS[kind]
                    return self.async_create_entry(
                        title=title,
                        data={
                            CONF_KIND: kind,
                            CONF_URL: url,
                            CONF_API_KEY: api_key,
                            CONF_VERIFY_SSL: verify_ssl,
                        },
                    )
        return self.async_show_form(step_id="user", data_schema=USER_SCHEMA, errors=errors)

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
        """Start reauthentication when the API key stops working."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Ask for a fresh API key and reload the entry on success."""
        entry = self._get_reauth_entry()
        errors: dict[str, str] = {}
        if user_input is not None:
            api_key = normalize_api_key(str(user_input.get(CONF_API_KEY, "")))
            if not api_key:
                errors["base"] = "invalid_input"
            else:
                client = ArrClient(
                    self.hass,
                    entry.data[CONF_URL],
                    api_key,
                    entry.data[CONF_KIND],
                    entry.data.get(CONF_VERIFY_SSL, DEFAULT_VERIFY_SSL),
                )
                try:
                    await client.async_validate()
                except ArrAuthError:
                    errors["base"] = "invalid_auth"
                except (ArrConnectionError, ArrResponseError):
                    errors["base"] = "cannot_connect"
                else:
                    return self.async_update_reload_and_abort(
                        entry,
                        data={**entry.data, CONF_API_KEY: api_key},
                        reason="reauth_successful",
                    )
        return self.async_show_form(step_id="reauth_confirm", data_schema=REAUTH_SCHEMA, errors=errors)


class ArrStudioOptionsFlow(OptionsFlow):
    """Handle Arr Studio options (plan §8.8)."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Collect the option values; saving reloads the entry via its update listener."""
        if user_input is not None:
            return self.async_create_entry(
                data={
                    CONF_SCAN_INTERVAL: int(user_input[CONF_SCAN_INTERVAL]),
                    CONF_RECENT_LIMIT: int(user_input[CONF_RECENT_LIMIT]),
                    CONF_LIBRARY_REFRESH: int(user_input[CONF_LIBRARY_REFRESH]),
                    CONF_SHOW_UNMONITORED: bool(user_input[CONF_SHOW_UNMONITORED]),
                    CONF_VERIFY_SSL: bool(user_input[CONF_VERIFY_SSL]),
                }
            )
        options = {**OPTIONS_DEFAULTS, **self.config_entry.options}
        schema = vol.Schema(
            {
                vol.Required(CONF_SCAN_INTERVAL, default=int(options[CONF_SCAN_INTERVAL])): selector.NumberSelector(
                    {"min": 15, "max": 600, "step": 5}
                ),
                vol.Required(CONF_RECENT_LIMIT, default=int(options[CONF_RECENT_LIMIT])): selector.NumberSelector(
                    {"min": 4, "max": 50, "step": 1}
                ),
                vol.Required(CONF_LIBRARY_REFRESH, default=int(options[CONF_LIBRARY_REFRESH])): selector.NumberSelector(
                    {"min": 5, "max": 60, "step": 1}
                ),
                vol.Required(CONF_SHOW_UNMONITORED, default=bool(options[CONF_SHOW_UNMONITORED])): selector.BooleanSelector(),
                vol.Required(CONF_VERIFY_SSL, default=bool(options[CONF_VERIFY_SSL])): selector.BooleanSelector(),
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
