# Arr Studio Architecture

Arr Studio is a Home Assistant custom integration for Sonarr and Radarr. It provides a full-screen sidebar panel with a cinematic design, poster grid of recently added media, live download activity with progress, per-server filters, newest-first ordering, and thumbnails served through Home Assistant.

## Overview

The integration consists of:
- **Config entry**: Per-Arr-server configuration with reauth and options
- **Coordinator**: Per-entry data update that polls Sonarr/Radarr API
- **Entity platforms**: Sensors, binary sensors, image, and button entities
- **Frontend panel**: A built-in `arr-studio-panel` custom element with Shadow DOM
- **API views**: `GET /api/arr_studio/overview` and `GET /api/arr_studio/cover/<entry>/<kind>/<media_id>/<variant>`

## Data Flow

1. User configures a server via the Home Assistant UI
2. `ArrStudioFlow` handles the config flow (and reauth); `async_setup_entry`
   creates the `ArrClient` and `ArrCoordinator` and stores them in
   `entry.runtime_data`
3. `ArrCoordinator` polls on a configurable interval (option `scan_interval`,
   default 30 s)
4. Every scan fetches `status`, `health`, `diskspace`, `queue` and `history`
   in parallel; the slower library endpoints (`series`/`movie`, `calendar`)
   refresh on a separate cadence (option `library_refresh`, default 10 min)
   and the last good library data is kept on refresh failure
5. Entities (sensors, binary sensor, image, button) observe the coordinator
   through `CoordinatorEntity`
6. The frontend panel polls `GET /api/arr_studio/overview` via
   `hass.fetchWithAuth` every 30 s while the page is visible (skipped when
   `document.hidden`); covers load lazily through
   `GET /api/arr_studio/cover/...` and are cached as blob URLs (max 200)

## Design Decisions

- Panel-first UI, not a Lovelace card: Cards registered via `frontend.add_extra_js_url()` are fire-and-forget and can lose the load-order race
- All lists come from an authenticated HTTP view, not entity attributes
- Cover images proxied by HA
- Two-speed polling (queue/history 30s, library/calendar 10min, cached)
- Pure-function normalisation (`normalize.py`) with fixtures for both apps
- `el()` DOM builder + Shadow DOM for XSS safety
- `integration_type: service`, `iot_class: local_polling`

## Key Files

- `custom_components/arr_studio/coordinator.py` - per-entry data update
- `custom_components/arr_studio/api.py` - authenticated HTTP client
- `custom_components/arr_studio/models.py` - frozen dataclasses
- `custom_components/arr_studio/normalize.py` - pure function normalisation
- `custom_components/arr_studio/config_flow.py` - config flow, options, reauth
- `custom_components/arr_studio/entity.py` - entity platforms
- `custom_components/arr_studio/frontend/panel.js` - built-in panel
- `custom_components/arr_studio/frontend/api.js` - overview fetch + cover blob cache
- `custom_components/arr_studio/frontend/dom.js` - DOM builder
- `custom_components/arr_studio/frontend/format.js` - format helpers
- `custom_components/arr_studio/frontend/icons.js` - inline SVG icons
- `custom_components/arr_studio/frontend/styles.js` - CSS
- `custom_components/arr_studio/frontend/state.js` - panel state
- `custom_components/arr_studio/frontend/render-*.js` - render functions
