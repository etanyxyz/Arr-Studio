"""HTTP views for the Arr Studio panel API and covers (plan §8.15)."""

from __future__ import annotations

import logging

from aiohttp import web
from homeassistant.components.http import KEY_HASS, HomeAssistantView
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from custom_components.arr_studio.api import (
    ArrAuthError,
    ArrError,
    ArrNotFoundError,
)
from custom_components.arr_studio.const import (
    ALLOWED_VARIANTS,
    COVER_URL_TEMPLATE,
    DATA_VIEWS_REGISTERED,
    DEFAULT_RECENT_LIMIT,
    DOMAIN,
    KINDS,
    OVERVIEW_URL,
)
from custom_components.arr_studio.payload import build_overview

_LOGGER = logging.getLogger(__name__)


def _not_found() -> web.Response:
    """404 JSON response, never cached."""
    return web.json_response(
        {"error": "not_found"}, status=404, headers={"Cache-Control": "no-store"}
    )


class ArrOverviewView(HomeAssistantView):
    """GET /api/arr_studio/overview — the overview payload for the panel."""

    url = OVERVIEW_URL
    name = "api:arr_studio:overview"
    requires_auth = True

    async def get(self, request: web.Request) -> web.Response:
        """Gather runtime data for loaded entries and return the payload."""
        hass: HomeAssistant = request.app[KEY_HASS]
        runtimes = []
        for entry in hass.config_entries.async_entries(DOMAIN):
            if entry.state is not ConfigEntryState.LOADED:
                continue
            runtime = getattr(entry, "runtime_data", None)
            if runtime is not None:
                runtimes.append(runtime)
        payload = build_overview(runtimes, DEFAULT_RECENT_LIMIT)
        return web.json_response(payload, headers={"Cache-Control": "no-store"})


class ArrCoverView(HomeAssistantView):
    """GET /api/arr_studio/cover/{entry_id}/{kind}/{media_id}/{variant}."""

    url = COVER_URL_TEMPLATE
    name = "api:arr_studio:cover"
    requires_auth = True

    async def get(
        self,
        request: web.Request,
        entry_id: str,
        kind: str,
        media_id: str,
        variant: str,
    ) -> web.Response:
        """Fetch a media cover image from the matching server."""
        hass: HomeAssistant = request.app[KEY_HASS]
        if kind not in KINDS or variant not in ALLOWED_VARIANTS:
            return _not_found()
        try:
            media = int(media_id)
        except (TypeError, ValueError):
            return _not_found()
        if media <= 0:
            return _not_found()

        entry = hass.config_entries.async_get_entry(entry_id)
        if entry is None or entry.domain != DOMAIN:
            return _not_found()
        runtime = getattr(entry, "runtime_data", None)
        if runtime is None or runtime.client.kind != kind:
            return _not_found()

        try:
            result = await runtime.client.async_get_cover(media, variant)
        except ArrNotFoundError:
            return _not_found()
        except ArrAuthError:
            return web.Response(status=403, headers={"Cache-Control": "no-store"})
        except ArrError:
            _LOGGER.debug("Arr Studio cover fetch failed", exc_info=True)
            return web.json_response(
                {"error": "upstream"}, status=502, headers={"Cache-Control": "no-store"}
            )
        if result is None:
            return _not_found()
        body, _content_type = result
        return web.Response(
            body=body,
            status=200,
            headers={
                "Cache-Control": "private, max-age=3600",
                "Content-Type": "image/jpeg",
            },
        )


def async_register_views(hass: HomeAssistant) -> None:
    """Register the overview and cover views once per HA instance."""
    if hass.data.get(DATA_VIEWS_REGISTERED):
        return
    hass.http.register_view(ArrOverviewView())
    hass.http.register_view(ArrCoverView())
    hass.data[DATA_VIEWS_REGISTERED] = True
