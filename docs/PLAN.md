# Arr Studio — Home Assistant integration for Sonarr & Radarr

**Status:** implementation plan v1.0
**Target repo:** https://github.com/etanyxyz/Arr-Studio (`main`)
**Integration domain:** `arr_studio`
**Target HA:** 2026.11.x (dev instance confirmed at 2026.11.2); minimum supported `2025.6.0`
**Author of plan:** build agent; **implementer:** local `ling-3.0-tiny` model

---

## 0. How to use this document (read this first, implementer)

You are a small model. This plan is deliberately prescriptive. Follow it literally.

Rules:

1. Work **one phase at a time**, in order. Do not start a phase until the previous phase's **Checkpoint** command passes.
2. **Do not invent** endpoints, fields, entity names, CSS class names, file names or function names. If something is missing, stop and ask.
3. **Do not add dependencies.** `manifest.json` requirements stay `[]`. Python: stdlib + HA + `aiohttp` (already in HA). JS: no npm, no build step, no external libraries, no CDN.
4. **Do not use `innerHTML`** with any dynamic value. Use the `el()` helper in `frontend/dom.js`. The only allowed literal HTML is static CSS assigned via `style.textContent`.
5. **Never print, log, return or embed the Arr API key** outside `api.py` request headers. Cover images are proxied by HA; the browser never sees the key.
6. Every value coming from Sonarr/Radarr is **untrusted**: use `.get()` with defaults, never assume a key exists, never assume a type.
7. Commit after each phase with the message given in the phase. Push to `origin main` using the SSH key at `/mnt/docker/Projects/github`.
8. If a checkpoint fails, fix that phase only. Do not "fix" it by weakening tests.
9. `docs/PLAN.md` is this file, verbatim. Never edit it.

Clone/push helper (run once):

```bash
export GIT_SSH_COMMAND="ssh -i /mnt/docker/Projects/github -o IdentitiesOnly=yes"
git clone git@github.com:etanyxyz/Arr-Studio.git
cd Arr-Studio
```

**Live credentials:** the human keeps real Sonarr/Radarr URLs and API keys in `.env` in the
repository root. `.env` is **git-ignored** and must never be committed, printed, or copied into
the integration. Only `scripts/live_smoke.py` reads it. Use `.env.example` as the template.
The integration itself is configured through the Home Assistant UI.

```bash
cp .env.example .env     # only if .env does not exist; never overwrite an existing one
python3 scripts/live_smoke.py
```

---

## 1. Product summary

**Arr Studio** is a single Home Assistant custom integration that connects to one or more
Sonarr and Radarr instances and provides:

1. Native HA entities for automation (queue counts, downloading count, library stats, missing
   count, disk free, health issues, online state, latest poster image, refresh button).
2. A **bundled, full-screen sidebar panel** (`Arr Studio`) that is the visual centrepiece:
   cinematic hero, poster grid of recently added media, live download activity with progress,
   per-server filters, newest-first ordering, thumbnails everywhere.
3. Thumbnails served **through Home Assistant** (the Arr API key is never exposed to the browser).
4. Marketplace/HACS-installable packaging: one repo, one integration, `hacs.json`, brand assets,
   CI validation, semver releases.

Non-goals for v0.1: adding/removing media, triggering searches, indexer/quality-profile editing,
Plex/Emby/Jellyfin integration, multi-user permissions, Lovelace dashboard strategy.

---

## 2. Scope

### 2.1 In scope (v0.1.0)

| Area | Deliverable |
|---|---|
| Config | UI config flow per Arr server, reauth, options flow |
| Data | Sonarr v4 + Radarr v5–v7 via `/api/v3` (live-verified: Sonarr 4.0.20.3014, Radarr 7.0.3.10918), 30 s activity poll, 10 min library cache |
| Entities | 8 sensors, 1 binary_sensor, 1 image, 1 button per configured server |
| UI | Sidebar panel `arr-studio`, glass/cinematic design, poster grid, queue, activity, filters, detail drawer |
| Media | Poster/fanart proxy with auth + caching; gradient placeholder fallback |
| Ops | Diagnostics (redacted), refresh service, structured logging, translations |
| Quality | ruff + pytest + preflight + hassfest + HACS Action, dev docker harness |

### 2.2 Explicitly out of scope

- Lovelace card or dashboard strategy (post-v0.1; see §15).
- Writing to Arr (no add/delete/search commands).
- Long-term statistics for library size (sensors are state-only).
- OAuth; Arr uses API keys only.

---

## 3. Key decisions (and why)

| # | Decision | Reason |
|---|---|---|
| D1 | **One config entry per Arr server** (not one combined entry) | Different URLs/keys, independent retries, standard HA pattern, reauth per server. |
| D2 | **Panel-first UI, not a Lovelace card** | Cards registered via `frontend.add_extra_js_url()` are fire-and-forget and can lose the load-order race ("Custom element doesn't exist"). A `panel_custom` module is loaded by the panel itself — deterministic, no resource step for the user. |
| D3 | **All lists come from an authenticated HTTP view** (`/api/arr_studio/overview`), not entity attributes | Large attributes are written to the recorder DB on every state change. Panels need rich lists; entities stay scalar. |
| D4 | **Cover images proxied by HA** (`/api/arr_studio/cover/...`) | Keeps `X-Api-Key` server-side; browser `<img>` gets a normal URL; panel uses `fetchWithAuth` + object URLs. |
| D5 | **Two-speed polling** (queue/history 30 s, library/calendar 10 min, cached) | Large `/series` / `/movie` payloads must not be fetched every 30 s. |
| D6 | **Pure-function normalisation** (`normalize.py`) with fixtures for both apps | Makes the tiny model's work testable without HA. |
| D7 | **No custom JS framework; `el()` DOM builder + Shadow DOM** | No build step, XSS-safe by construction, ~150-line modules the model can generate reliably. |
| D8 | **`integration_type: service`, `iot_class: local_polling`** | Correct semantics for a local server integration. |
| D9 | **Real credentials live in a git-ignored `.env`, never in the repo or the integration** | Enables validation against the human's live Sonarr/Radarr without leaking keys; `.env.example` documents the keys; preflight verifies `.env` is ignored and untracked. |
| D10 | **Covers are lazy-loaded and cached** (`IntersectionObserver`, blob URL cache, `Cache-Control: private, max-age=3600`) | Live posters are 0.4–1.3 MB each; eager loading a 24-poster grid would stall the panel. |

---

## 4. Verified external API reference

All calls: `GET {base_url}/api/v3/<path>`, header `X-Api-Key: <key>`, `Accept: application/json`.
Base URL is normalised (no trailing slash, no `/api` or `/api/v3` suffix). HTTPS optional;
`verify_ssl` configurable.

### 4.1 Endpoints used

| Purpose | Sonarr | Radarr | Query params |
|---|---|---|---|
| Identity/version | `/api/v3/system/status` | same | — |
| Health | `/api/v3/health` | same | — |
| Disk space | `/api/v3/diskspace` | same | — |
| Queue | `/api/v3/queue` | same | `page=1&pageSize=100&sortKey=timeleft&sortDirection=ascending&includeSeries=true&includeEpisode=true` (Radarr: `includeMovie=true`) |
| History | `/api/v3/history` | same | `page=1&pageSize=20&sortKey=date&sortDirection=descending&includeSeries=true&includeEpisode=true` (Radarr: `includeMovie=true`) |
| Library | `/api/v3/series` | `/api/v3/movie` | — |
| Calendar | `/api/v3/calendar` | same | `start=YYYY-MM-DD&end=YYYY-MM-DD&includeSeries=true` (Radarr: `includeMovie=true`) |
| Poster/fanart | `/api/v3/mediacover/{id}/{variant}.jpg` | same | `variant` ∈ `poster`, `fanart`, `banner` |

Verified in source: `src/Sonarr.Api.V3/MediaCovers/MediaCoverController.cs` route is
`{seriesId:int}/{filename:regex((.+)\.(jpg|png|gif))}`; queue controller accepts the params above.

### 4.2 Response shapes (fields we rely on)

**`/system/status`**
```json
{"appName":"Sonarr","instanceName":"Sonarr","version":"4.0.15.2941","startTime":"...","osName":"..."}
```

**`/queue`** → `PagingResource`:
```json
{"page":1,"pageSize":100,"sortKey":"timeleft","sortDirection":"ascending","totalRecords":2,
 "records":[{"id":1201,"seriesId":34,"episodeId":9001,"seasonNumber":2,
  "title":"Severance.S02E04.1080p.WEB-DL","status":"downloading","trackedDownloadState":"downloading",
  "trackedDownloadStatus":"ok","size":1825361100,"sizeleft":1056964608,
  "timeleft":"00:05:12","estimatedCompletionTime":"2026-11-23T16:05:12Z","added":"2026-11-23T15:40:00Z",
  "protocol":"torrent","downloadClient":"qBittorrent","indexer":"TorrentLeech",
  "quality":{"quality":{"id":3,"name":"WEBDL-1080p"}},"errorMessage":null,
  "series":{"id":34,"title":"Severance","titleSlug":"severance","year":2022,"images":[...]},
  "episode":{"seasonNumber":2,"episodeNumber":4,"title":"Woe's Hollow"}}]}
```
Radarr records use `movieId` + `movie` instead of `seriesId`/`series`/`episode`, and have
`movieFile`-less fields; the same `size`/`sizeleft`/`timeleft`/`status`/`protocol` keys apply.

**`/history`** → `PagingResource` with `records`:
`id`, `date`, `eventType` (`grabbed`, `downloadFolderImported`, `downloadFailed`,
`episodeFileDeleted`, `episodeFileRenamed` / movie equivalents), `sourceTitle`,
`quality.quality.name`, `data{}`, `series{}`/`episode{}` or `movie{}` when includes requested.

**`/series`** → array; fields used: `id`, `title`, `titleSlug`, `year`, `added`, `monitored`,
`status`, `network`, `genres`, `overview`, `images[]`, `statistics{episodeCount, episodeFileCount,
totalEpisodeCount, sizeOnDisk, percentOfEpisodes}`, `nextAiring`.

**`/movie`** → array; fields used: `id`, `title`, `titleSlug`, `year`, `added`, `monitored`,
`hasFile`, `sizeOnDisk`, `status`, `runtime`, `genres`, `studio`, `overview`, `images[]`,
`movieFile.quality.quality.name`.

**`images[]` item:** `{"coverType":"poster","url":"/MediaCover/34/poster.jpg?lastWrite=...","remoteUrl":"https://image.tmdb.org/..."}`.
`coverType` values seen: `poster`, `fanart`, `banner`, `logo`, `clearlogo`. We use `poster`, `fanart`.

**`/diskspace`** → `[{"path":"/tv","label":"tv","freeSpace":872000000000,"totalSpace":4000000000000}]`
**`/health`** → `[{"source":"IndexerLongTermStatusCheck","type":"warning","message":"...","wikiUrl":"..."}]`
**`/calendar`** → array of series/movie objects with `airDateUtc`/`digitalRelease`/`physicalRelease`.

### 4.3 Field-availability rules

- `sizeleft` and `timeleft` are serialised **lowercase** (legacy names in `QueueResource`), and
  `timeleft` is a `TimeSpan` string: `HH:MM:SS` or `d.HH:MM:SS`. Prefer
  `estimatedCompletionTime`; parse `timeleft` only as fallback.
- `images` may be `null`, `[]`, or missing. `remoteUrl` may be `null`.
- Statistics may be missing on freshly added items. Never divide without a guard.
- `status` strings differ between apps. Treat any value not in our known set as `unknown`.
- Timestamps are ISO-8601 with `Z`; parse with `datetime.fromisoformat(v.replace("Z", "+00:00"))`.

### 4.4 Live verification (2026-11-23, real servers)

`scripts/live_smoke.py` ran successfully against both servers:

| | Sonarr | Radarr |
|---|---|---|
| Version | 4.0.20.3014 | 7.0.3.10918 |
| Transport | HTTP, no TLS | HTTP, no TLS |
| Library | 15 series | 3 movies |
| Queue at test time | 0 records | 0 records |
| Health | 1 warning | 3 issues (1 error, 2 warnings) |
| History (latest page) | 1439 total; `downloadFolderImported` | 4 total; `downloadFolderImported`, `grabbed` |
| Poster route | `200 image/jpeg`, 409 KB | `200 image/jpeg`, 1.3 MB |
| Calendar (14 days) | 0 | 0 |

Consequences for the implementation:

1. **Posters are large** (up to ~1.3 MB each). Covers MUST be lazy-loaded with
   `IntersectionObserver` (`rootMargin: "200px"`) and cached as blob object URLs (max 200); never
   fetch the whole grid eagerly. The cover response sets `Cache-Control: private, max-age=3600`.
2. **`/queue` was empty**, so queue field names are proven by the repository fixtures and the
   controller source, not by this run. Keep `tests/fixtures/*_queue.json` realistic and keep the
   tolerant `.get()` normalisation.
3. **`/diskspace` reports the filesystem the Arr process sees** (Sonarr reported `/`, 105 GB, not
   the host array). Label the sensor "Disk free" with the reported `path` attribute; do not claim it
   is the host's media pool.
4. **`/calendar` can legitimately return 0 items.** The Upcoming UI needs a real empty state, and
   `counts["upcoming"]` must be 0, not an error.
5. **History may contain only import events on some servers.** Activity UI must render any unknown
   `eventType` as a humanised fallback ("Grabbed", "Imported", "Failed", else the raw string
   with underscores replaced).
6. **`coverType` values in the wild:** `poster`, `fanart`, `banner`, `clearlogo`. Only `poster` and
   `fanart` are used; treat missing art as a normal condition.
7. Radarr 7 still serves `/api/v3`; the `includeMovie=true` queue parameter was accepted. No
   version branching is needed.

---

## 5. Architecture

```
                    ┌──────────────────────────── HA process ────────────────────────────┐
Browser             │                                                                   │
  │  GET /arr-studio (panel)                                                          │
  ├────────────────►│ frontend panel_custom  ── module_url: /arr_studio/panel.js         │
  │                 │        (static file from custom_components/arr_studio/frontend)   │
  │  GET /api/arr_studio/overview   (fetchWithAuth, Bearer token)                      │
  ├────────────────►│ ArrOverviewView ── reads coordinator.data of every loaded entry    │
  │  GET /api/arr_studio/cover/<entry>/<kind>/<id>/<variant>                           │
  ├────────────────►│ ArrCoverView ── X-Api-Key ──► Sonarr/Radarr /api/v3/mediacover/... │
  │                 │                                                                   │
  │                 │ ArrCoordinator (per entry)                                        │
  │                 │   poll 30 s: status(cached 1 h) health diskspace queue history     │
  │                 │   every 10 min: series|movie + calendar (in-memory cache)         │
  │                 └───────────────┬───────────────────────────────┬───────────────────┘
  │                                 │                               │
  │                        sensor.* / binary_sensor.* / image.*      │
  │                        (scalar state + ≤5 scalar attributes)     │
  └─────────────────────────────────┴──────────► Sonarr / Radarr HTTP API
```

**Freshness:** panel polls `overview` every 30 s (paused when tab hidden). Entities update via
coordinator listeners. Button + `arr_studio.refresh` force an immediate coordinator refresh.

**Failure model:** 401/403 → `ConfigEntryAuthFailed` → reauth flow. Network/5xx → `UpdateFailed`
→ entities unavailable, panel shows per-server error banner but keeps last good data.
Cover 404 → 404 to browser → panel renders gradient placeholder.

---

## 6. Repository layout

```
Arr-Studio/
├─ .github/workflows/validate.yml
├─ .gitignore                   (ignores .env and .env.local; keeps .env.example)
├─ .env.example                 (placeholders for SONARR_/RADARR_ URL + API key)
├─ hacs.json
├─ info.md
├─ LICENSE                      (MIT, "Copyright (c) 2026 etanyxyz")
├─ README.md
├─ pyproject.toml               (ruff + pytest config only)
├─ docs/
│  ├─ PLAN.md                   (this file, verbatim)
│  ├─ ARCHITECTURE.md
│  ├─ UI.md                     (design tokens + screenshots)
│  ├─ TESTING.md
│  └─ images/                   (screenshots, added in Phase 7)
├─ examples/
│  └─ automation-download-complete.yaml
├─ custom_components/arr_studio/
│  ├─ __init__.py
│  ├─ api.py
│  ├─ binary_sensor.py
│  ├─ button.py
│  ├─ config_flow.py
│  ├─ const.py
│  ├─ coordinator.py
│  ├─ diagnostics.py
│  ├─ entity.py
│  ├─ frontend.py
│  ├─ http_views.py
│  ├─ image.py
│  ├─ manifest.json
│  ├─ models.py
│  ├─ normalize.py
│  ├─ payload.py
│  ├─ sensor.py
│  ├─ services.py
│  ├─ strings.json
│  ├─ translations/en.json
│  ├─ brand/
│  │  ├─ icon.png              (256×256)
│  │  └─ logo.png              (512×256, transparent)
│  └─ frontend/
│     ├─ panel.js              entry module, defines <arr-studio-panel>
│     ├─ api.js                overview fetch + cover blob cache
│     ├─ dom.js                el()/svg()/clear() helpers (no innerHTML)
│     ├─ format.js             bytes, eta, relative time, text helpers
│     ├─ icons.js              inline SVG strings (static, trusted)
│     ├─ styles.js             BASE_CSS string
│     ├─ state.js              panel state (tab/kind/query/sort) + localStorage
│     ├─ render-hero.js        header + stat pills + disk ring
│     ├─ render-recent.js      poster grid + detail drawer
│     ├─ render-queue.js       download rows + progress
│     ├─ render-activity.js    completed imports feed
│     └─ placeholder.svg       fallback artwork (static)
├─ scripts/
│  ├─ preflight.py             repo/manifest/translation/security checks
│  ├─ check_frontend.mjs       node syntax + forbidden-pattern check
│  ├─ live_smoke.py            validates real servers using .env (stdlib only, never prints keys)
│  └─ make_brand_assets.py     deterministic PIL icon/logo generator
└─ tests/
   ├─ conftest.py
   ├─ fixtures/
   │  ├─ sonarr_series.json
   │  ├─ sonarr_queue.json
   │  ├─ sonarr_history.json
   │  ├─ sonarr_status.json
   │  ├─ sonarr_diskspace.json
   │  ├─ radarr_movie.json
   │  ├─ radarr_queue.json
   │  └─ radarr_history.json
   ├─ test_api.py
   ├─ test_normalize.py
   ├─ test_payload.py
   └─ test_format.py
```

`custom_components/arr_studio/frontend/` is the only folder shipped to users' HA, so all JS lives
there (Marketplace installs only that folder).

---

## 7. Build phases, tasks and checkpoints

### Phase 0 — Bootstrap (commit `chore: repo scaffold`)

1. Create every directory in §6.
2. Write `.gitignore`. It **must** contain, at minimum:
   ```
   # Secrets — never commit
   .env
   .env.local
   .env.*.local
   !.env.example

   __pycache__/
   *.py[cod]
   .venv/
   .pytest_cache/
   .ruff_cache/
   .mypy_cache/
   node_modules/
   dev/config/.storage/
   dev/config/home-assistant.log*
   dev/config/*.db
   dev/config/*.db-*
   .DS_Store
   ```
3. Write `.env.example` with `SONARR_URL`, `SONARR_API_KEY`, `RADARR_URL`, `RADARR_API_KEY`
   placeholders and a comment stating that `.env` is git-ignored and used only by
   `scripts/live_smoke.py`. **Never create, overwrite, read or commit `.env` yourself.**
4. Write `LICENSE` (MIT, "Copyright (c) 2026 etanyxyz"), `hacs.json` per §8.2,
   `pyproject.toml` (ruff: `select = ["E","F","W","I"]`, `line-length = 100`; pytest
   `testpaths = ["tests"]`), `README.md` skeleton (title, one-paragraph description, feature
   bullets, `## Installation` placeholder, `## Screenshots` placeholder, `## Development` link to
   `docs/TESTING.md`, MIT + not-affiliated disclaimer), `info.md`.
5. Write `scripts/preflight.py` per §8.19, `scripts/check_frontend.mjs` per §8.20 and
   `scripts/live_smoke.py` per §13.1.
6. Copy this plan to `docs/PLAN.md`.

**Checkpoint 0**
```bash
python3 scripts/preflight.py --phase 0
node scripts/check_frontend.mjs          # prints SKIP: no JS yet
ruff check scripts 2>/dev/null || true
python3 scripts/live_smoke.py || true    # optional; requires .env, never prints keys
```
Expected: preflight `all N checks passed`, including `.env ignored` and `.env not tracked`.

---

### Phase 1 — API client + normalisation + fixtures (commit `feat: arr api client`)

Implement `const.py`, `api.py`, `models.py`, `normalize.py`; create the 8 fixture JSON files from
real captured responses (sanitise titles if desired, keep structure identical).

**Checkpoint 1**
```bash
ruff check custom_components tests
pytest tests/test_api.py tests/test_normalize.py -q
```

---

### Phase 2 — Integration core (commit `feat: config flow and coordinator`)

Implement `manifest.json`, `strings.json`, `translations/en.json`, `coordinator.py`,
`config_flow.py`, `entity.py`, `__init__.py`, `diagnostics.py`, `services.py`.

**Checkpoint 2**
```bash
python3 -m compileall -q custom_components/arr_studio
python3 scripts/preflight.py --phase 2
pytest tests -q
```

---

### Phase 3 — Entity platforms (commit `feat: entities`)

Implement `sensor.py`, `binary_sensor.py`, `image.py`, `button.py`.

**Checkpoint 3**
```bash
python3 scripts/preflight.py --phase 3
pytest tests -q
```

Manual check in dev harness (§13): add mock Sonarr, confirm 10 entities appear, no tracebacks.

---

### Phase 4 — HTTP API (commit `feat: authenticated overview and cover api`)

Implement `payload.py`, `http_views.py`; register views in `async_setup`.

**Checkpoint 4**
```bash
pytest tests/test_payload.py -q
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8123/api/arr_studio/overview   # expect 401
```

---

### Phase 5 — Frontend panel (commit `feat: arr studio panel`)

Implement `styles.js` → `dom.js` → `format.js` → `icons.js` → `api.js` → `state.js` →
`render-hero.js` → `render-queue.js` → `render-recent.js` → `render-activity.js` → `panel.js`
→ `frontend.py`; generate brand assets with `scripts/make_brand_assets.py`.

**Checkpoint 5**
```bash
node scripts/check_frontend.mjs
python3 scripts/preflight.py --phase 5
```
Browser: panel visible in sidebar, covers render, tabs switch, no console errors, 390/768/1440 px.

---

### Phase 6 — Docs, CI, examples, release (commit `docs: documentation and release prep`)

Write `README.md` (full), `info.md`, `docs/ARCHITECTURE.md`, `docs/UI.md`, `docs/TESTING.md`,
`examples/automation-download-complete.yaml`, `.github/workflows/validate.yml`.
Tag `v0.1.0`, create a GitHub release; manifest version must equal the tag.

**Checkpoint 6**
```bash
ruff check . && pytest -q && node scripts/check_frontend.mjs
git tag v0.1.0 && git push origin main --tags
```
GitHub Actions: Validate (lint+pytest+node), hassfest, HACS Action — all green.

---

### Phase 7 — Screenshots & acceptance (commit `docs: screenshots`)

Capture `docs/images/panel-overview.png`, `panel-downloads.png`, `panel-detail.png`,
`entities.png` at 1440×900 and one mobile 390×844. Run the full acceptance list in §14.
Optional: short GIF/MP4 of the panel (`docs/images/demo.gif`, < 8 MB).

---

## 8. File specifications

### 8.1 `manifest.json`

```json
{
  "domain": "arr_studio",
  "name": "Arr Studio",
  "codeowners": ["@etanyxyz"],
  "config_flow": true,
  "dependencies": ["http", "frontend"],
  "documentation": "https://github.com/etanyxyz/Arr-Studio",
  "integration_type": "service",
  "iot_class": "local_polling",
  "issue_tracker": "https://github.com/etanyxyz/Arr-Studio/issues",
  "loggers": ["custom_components.arr_studio"],
  "requirements": [],
  "version": "0.1.0"
}
```

### 8.2 `hacs.json`

```json
{
  "name": "Arr Studio",
  "homeassistant": "2025.6.0",
  "render_readme": true
}
```

### 8.3 `const.py`

```python
DOMAIN = "arr_studio"
NAME = "Arr Studio"
VERSION = "0.1.0"

KIND_SONARR = "sonarr"
KIND_RADARR = "radarr"
KINDS = (KIND_SONARR, KIND_RADARR)
KIND_LABELS = {KIND_SONARR: "Sonarr", KIND_RADARR: "Radarr"}

CONF_KIND = "kind"
CONF_URL = "url"
CONF_API_KEY = "api_key"
CONF_VERIFY_SSL = "verify_ssl"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_RECENT_LIMIT = "recent_limit"
CONF_LIBRARY_REFRESH = "library_refresh"
CONF_SHOW_UNMONITORED = "show_unmonitored"

DEFAULT_SCAN_INTERVAL = 30          # seconds, 15..600
DEFAULT_RECENT_LIMIT = 12           # 4..50 per server
DEFAULT_LIBRARY_REFRESH = 10        # minutes, 5..60
DEFAULT_VERIFY_SSL = True
DEFAULT_SHOW_UNMONITORED = False

API_PATH = "/api/v3"
REQUEST_TIMEOUT = 20

OVERVIEW_URL = "/api/arr_studio/overview"
COVER_URL_TEMPLATE = "/api/arr_studio/cover/{entry_id}/{kind}/{media_id}/{variant}"
ALLOWED_VARIANTS = ("poster", "fanart", "banner")

PANEL_URL_PATH = "arr-studio"
PANEL_ELEMENT = "arr-studio-panel"
PANEL_TITLE = "Arr Studio"
PANEL_ICON = "mdi:filmstrip-box-multiple"
FRONTEND_STATIC_URL = "/arr_studio"
FRONTEND_ENTRY = "arr-studio-panel.js"
DATA_FRONTEND_REGISTERED = f"{DOMAIN}_frontend_registered"
DATA_VIEWS_REGISTERED = f"{DOMAIN}_views_registered"

SERVICE_REFRESH = "refresh"

PLATFORMS = ["sensor", "binary_sensor", "image", "button"]
```

### 8.4 `api.py`

```python
class ArrError(Exception): ...
class ArrAuthError(ArrError): ...
class ArrConnectionError(ArrError): ...
class ArrResponseError(ArrError): ...
class ArrNotFoundError(ArrError): ...

def normalize_base_url(value: str) -> str
def normalize_api_key(value: str) -> str          # strip whitespace/newlines

class ArrClient:
    def __init__(self, hass, base_url, api_key, kind, verify_ssl=True) -> None
    async def async_get_status(self) -> dict
    async def async_get_health(self) -> list[dict]
    async def async_get_diskspace(self) -> list[dict]
    async def async_get_queue(self, page_size: int = 100) -> list[dict]
    async def async_get_history(self, page_size: int = 20) -> list[dict]
    async def async_get_library(self) -> list[dict]
    async def async_get_calendar(self, days: int = 14) -> list[dict]
    async def async_get_cover(self, media_id: int, variant: str = "poster") -> tuple[bytes, str] | None
    async def async_validate(self) -> dict        # status + appName check
```

Rules:
- Use `homeassistant.helpers.aiohttp_client.async_get_clientsession(self._hass, verify_ssl=...)`.
- Headers per request: `{"X-Api-Key": self._api_key, "Accept": "application/json"}`; cover request uses
  `Accept: image/*, */*`.
- Timeout `aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)`.
- Map status: 401/403 → `ArrAuthError`; 404 → `ArrNotFoundError`; other >=400 → `ArrResponseError`
  (include status + path, **never** the key or response body that may echo headers); `aiohttp.ClientError`,
  `TimeoutError`, `asyncio.TimeoutError` → `ArrConnectionError`.
- Queue URL params per §4.1; `includeMovie` for radarr, `includeSeries`/`includeEpisode` for sonarr.
- `async_get_library` returns `records` for series/movie arrays (they are bare arrays).
- `async_get_cover`: build `f"{base}{API_PATH}/mediacover/{media_id}/{variant}.jpg"`; `variant` must be
  in `ALLOWED_VARIANTS`; return `(body, content_type)` or `None` on 404.
- `async_validate`: fetch status; if `status.get("appName","").lower() != kind` raise
  `ArrResponseError(f"Expected {kind}, got {app_name}")`; return status.
- Logging: log URL path only at debug, never the key, never full cover bytes.

### 8.5 `models.py`

Frozen dataclasses; all fields have defaults where possible. `to_dict()` returns JSON-safe primitives.

```python
@dataclass(frozen=True, slots=True)
class MediaItem:
    entry_id: str; kind: str; id: int; title: str
    subtitle: str = ""; year: int | None = None
    added: str | None = None            # ISO-8601 Z
    poster: str | None = None           # /api/arr_studio/cover/... path
    fanart: str | None = None
    monitored: bool = True; has_file: bool = False
    size: int = 0; quality: str | None = None
    overview: str = ""; meta: tuple[str, ...] = ()
    web_url: str | None = None

@dataclass(frozen=True, slots=True)
class QueueItem:
    entry_id: str; kind: str; id: int; title: str
    subtitle: str = ""; poster: str | None = None
    progress: float | None = None       # 0..1
    size: int = 0; size_left: int = 0
    eta_seconds: int | None = None
    speed_bps: int | None = None
    status: str = "unknown"; state: str = "unknown"
    protocol: str | None = None; client: str | None = None
    quality: str | None = None; error: str | None = None
    added: str | None = None; web_url: str | None = None

@dataclass(frozen=True, slots=True)
class ActivityItem:
    entry_id: str; kind: str; id: int; event: str
    title: str; subtitle: str = ""; date: str | None = None
    poster: str | None = None; quality: str | None = None; web_url: str | None = None

@dataclass(frozen=True, slots=True)
class DiskInfo:
    path: str; free: float = 0.0; total: float = 0.0
    @property
    def used_pct(self) -> float | None: ...

@dataclass(frozen=True, slots=True)
class ServerSnapshot:
    entry_id: str; kind: str; name: str; version: str | None
    online: bool; error: str | None
    library: tuple[MediaItem, ...]; recent: tuple[MediaItem, ...]
    queue: tuple[QueueItem, ...]; activity: tuple[ActivityItem, ...]
    disk: DiskInfo | None
    counts: dict[str, int]; health: tuple[dict, ...] = ()
    speed_bps: int = 0
    updated_at: str | None = None
```

`counts` keys: `library`, `queue`, `downloading`, `recent`, `missing`, `upcoming`, `health`.

### 8.6 `normalize.py`

Pure functions, no HA imports, no I/O.

```python
def cover_path(entry_id: str, kind: str, media_id: int, variant: str) -> str
def pick_image(images: list | None, cover_type: str) -> str | None      # returns remoteUrl
def iso_utc(value: str | None) -> str | None
def compute_progress(size, size_left) -> float | None
def parse_timeleft(value: str | None) -> int | None                    # seconds
def parse_datetime(value: str | None) -> datetime | None
def normalize_series(entry_id: str, raw: dict, base_url: str) -> MediaItem
def normalize_movie(entry_id: str, raw: dict, base_url: str) -> MediaItem
def normalize_queue(entry_id: str, kind: str, raw: dict, base_url: str) -> QueueItem
def normalize_history(entry_id: str, kind: str, raw: dict, base_url: str) -> ActivityItem | None
def normalize_health(raw: list | None) -> tuple[dict, ...]             # keep source/type/message only
def normalize_disks(raw: list | None) -> tuple[DiskInfo, ...]
def compute_missing(kind: str, library: list[dict], show_unmonitored: bool) -> int
def merge_counts(...) -> dict[str, int]
def web_url(kind: str, base_url: str, title_slug: str | None) -> str | None
```

Rules:
- `title` fallback: `raw.get("title") or raw.get("sortTitle") or "Unknown"`.
- `subtitle`:
  - series library item: `f"{network} · {year}"` if network else year.
  - movie: `f"{studio} · {year}"` if studio else year.
  - queue series: `f"S{season:02d}E{episode:02d} · {episode_title}"` when available; else queue title.
  - queue movie: year.
  - history: same as queue where possible, else `sourceTitle`.
- `poster`/`fanart` are **HA paths** built with `cover_path`; also verify the raw item actually has that
  image (`pick_image`); if not, set `None` (panel falls back to gradient). Exception: queue items may have
  no series/movie images inline — then use `/api/arr_studio/cover/...` anyway; cover view resolves it and
  404 → placeholder.
- All strings trimmed; truncate `overview` to 600 chars; `meta` = first 3 of `genres` plus network/studio.
- Sort helper `sort_newest_first(items)` by `added` desc with `None` last, stable tiebreak by title.

### 8.7 `coordinator.py`

```python
@dataclass
class ArrRuntimeData:
    client: ArrClient
    coordinator: ArrCoordinator

class ArrCoordinator(DataUpdateCoordinator[ServerSnapshot]):
    def __init__(self, hass, entry, client, scan_interval, recent_limit,
                 library_refresh_minutes, show_unmonitored) -> None
    async def _async_update_data(self) -> ServerSnapshot
```

`_async_update_data` sequence (use `asyncio.gather` for independent calls, `return_exceptions=True`):

1. `status` — cached in `self._status` for 3600 s; on failure reuse cached, else `None`.
2. `health`, `diskspace`, `queue`, `history` — every poll.
3. If `now >= self._library_due`: `library`, `calendar`; update `self._library` and `self._calendar`,
   set `_library_due = now + minutes`. On failure keep previous cache and log a warning.
4. Build `MediaItem`s from library → sort newest first → `recent = items[:recent_limit]`.
5. Merge queue items; compute `speed_bps` from byte deltas keyed by `downloadId`:
   `delta_bytes = max(0, prev_size_left - size_left)`, `speed = 0.7 * prev + 0.3 * (delta/dt)`;
   zero when queue empty or dt > 300 s. Keep `self._speed_state: dict[str, tuple[float, float]]`.
6. `counts` via `compute_missing` etc.
7. Return `ServerSnapshot(...)`; `online=True`, `error=None`.
8. On `ArrAuthError` → `raise ConfigEntryAuthFailed` (import from `homeassistant.exceptions`).
   On `ArrConnectionError`/`ArrResponseError` → `raise UpdateFailed(str(err))` (message must not contain
   the API key). On repeated failure keep serving nothing; entities become unavailable automatically.

Also expose `def cover(self, media_id, variant)` delegating to client for the HTTP view, and
`async def async_force_refresh()` → `await self.async_request_refresh()`.

Constants: `update_interval=timedelta(seconds=scan_interval)`, `config_entry=entry`,
`always_update=False`, `name=f"Arr Studio {kind.title()}"`.

### 8.8 `config_flow.py`

Steps:

- `async_step_user`: form fields `kind` (SelectSelector: sonarr/radarr), `url` (TextSelector URL),
  `api_key` (TextSelector PASSWORD), `verify_ssl` (BooleanSelector, default True).
  On submit:
  1. `url = normalize_base_url(...)`, `api_key = normalize_api_key(...)`.
  2. If either empty → `errors["base"] = "invalid_input"`.
  3. `client = ArrClient(hass, ...)`; `status = await client.async_validate()`.
  4. Exceptions → `cannot_connect` / `invalid_auth` / `wrong_server` (appName mismatch).
  5. `await self.async_set_unique_id(f"{kind}_{url}", raise_on_progress=False)`;
     `self._abort_if_unique_id_configured(updates={CONF_API_KEY: api_key})`.
  6. Title: `status.get("instanceName") or KIND_LABELS[kind]`.
  7. `async_create_entry(title=title, data={kind,url,api_key,verify_ssl})`.
- `async_step_reauth` / `async_step_reauth_confirm`: single password field; on success
  `async_update_reload_and_abort(entry, data={**entry.data, CONF_API_KEY: key})`.
- `async_step_import` (optional): accept YAML import for migration; not required — omit in v0.1.
- `OptionsFlowHandler`: `scan_interval` (NumberSelector 15..600, step 5), `recent_limit`
  (NumberSelector 4..50), `library_refresh` (NumberSelector 5..60), `show_unmonitored`
  (BooleanSelector), `verify_ssl` (BooleanSelector). Save → `async_create_entry(data=...)`;
  `__init__.py` update listener reloads the entry.

Errors/aborts in `strings.json`: `cannot_connect`, `invalid_auth`, `wrong_server`, `invalid_input`,
`unknown`; abort `already_configured`, `reauth_successful`.

### 8.9 `entity.py`

```python
class ArrEntity(CoordinatorEntity[ArrCoordinator]):
    _attr_has_entity_name = True
    def __init__(self, coordinator: ArrCoordinator, key: str) -> None
    @property def device_info(self) -> DeviceInfo
    @property def available(self) -> bool
    def _snapshot(self) -> ServerSnapshot
```

`device_info`:
```python
{
  "identifiers": {(DOMAIN, entry.entry_id)},
  "name": coordinator.config_entry.title,
  "manufacturer": KIND_LABELS[kind],
  "model": f"{KIND_LABELS[kind]} {version or ''}".strip(),
  "sw_version": version,
  "configuration_url": base_url,
  "entry_type": DeviceEntryType.SERVICE,
}
```
Unique IDs: `f"{entry.entry_id}_{key}"`. Suggested object IDs are automatic from `_attr_name`.

### 8.10 `sensor.py`

| key | name | state | unit | device_class | icon | attributes (≤5 scalars) |
|---|---|---|---|---|---|---|
| `queue` | Queue | `counts["queue"]` | — | — | `mdi:download-network` | `downloading` |
| `downloading` | Downloading | `counts["downloading"]` | — | — | `mdi:progress-download` | `speed` (MB/s, 2 dp) |
| `recent` | Recent additions | `counts["recent"]` | — | — | `mdi:new-box` | `latest_title`, `latest_added` |
| `library` | Library | `counts["library"]` | — | — | `mdi:movie-open` | `shows`/`movies` (one of), `size_gb` |
| `missing` | Missing | `counts["missing"]` | — | — | `mdi:alert-circle-outline` | `monitored_only` |
| `disk_free` | Disk free | rounded GiB (1 dp) | `GiB` | `DATA_SIZE` | `mdi:harddisk` | `path`, `total_gb`, `used_pct` |
| `health` | Health issues | `counts["health"]` | — | — | `mdi:stethoscope` | `worst` (`error`/`warning`/`ok`) |

`state_class` only on `disk_free` (`MEASUREMENT`). Do **not** put lists in attributes.
`disk_free` uses the volume with the largest `total`; expose that volume's `path` in attributes.

### 8.11 `binary_sensor.py`

- key `online`, name "Online", `device_class=CONNECTIVITY`, state `snapshot.online`.
- attributes: `last_update` (ISO string), `error` (short scalar, may be None).

### 8.12 `image.py`

- key `latest_poster`, name "Latest poster".
- `_attr_content_type = "image/jpeg"`.
- `image_last_updated` = snapshot `updated_at` parsed datetime, or `None`.
- `async_image()`: if no recent item → read bundled `frontend/placeholder.svg` bytes and set
  `image/svg+xml`; else `await coordinator.client.async_get_cover(item.id, "poster")`; on `None` →
  placeholder. Wrap in try/except `ArrError` → placeholder (never raise from `async_image`).
- `extra_state_attributes`: `title`, `kind`, `item_id` (scalars only).
- Entity id example: `image.sonarr_latest_poster`.

### 8.13 `button.py`

- key `refresh`, name "Refresh", `_attr_icon = "mdi:refresh"`.
- `async_press()` → `await self.coordinator.async_request_refresh()`.

### 8.14 `payload.py`

```python
def build_overview(runtimes: list[ArrRuntimeData], recent_limit: int) -> dict
```

Output contract (exact keys; panel depends on them):

```json
{
  "version": 1,
  "generated_at": "2026-11-23T16:00:00+00:00",
  "servers": [{
    "entry_id": "...", "kind": "sonarr", "name": "Sonarr", "version": "4.0.15.2941",
    "online": true, "error": null, "web_url": "http://192.168.1.10:8989",
    "counts": {"library":34,"queue":2,"downloading":2,"recent":12,"missing":87,"upcoming":4,"health":0},
    "disk": {"path":"/tv","free":812.4,"total":3726.0,"used_pct":78.2},
    "speed_bps": 12400000
  }],
  "recent": [{
    "key":"sonarr:34","entry_id":"...","kind":"sonarr","id":34,
    "title":"Severance","subtitle":"Apple TV+ · 2022","year":2022,
    "added":"2026-11-23T14:02:11Z",
    "poster":"/api/arr_studio/cover/.../sonarr/34/poster",
    "fanart":"/api/arr_studio/cover/.../sonarr/34/fanart",
    "monitored":true,"has_file":true,"size":4823449600,
    "quality":"WEBDL-1080p","overview":"Mark leads a team...",
    "meta":["Sci-Fi","Drama","Apple TV+"],
    "web_url":"http://192.168.1.10:8989/series/severance"
  }],
  "queue": [{
    "key":"sonarr:1201","entry_id":"...","kind":"sonarr","id":1201,
    "title":"Severance","subtitle":"S02E04 · Woe's Hollow",
    "poster":"/api/arr_studio/cover/.../sonarr/34/poster",
    "progress":0.42,"size":1825361100,"size_left":1056964608,"eta_seconds":312,
    "speed_bps":6200000,"status":"downloading","state":"downloading",
    "protocol":"torrent","client":"qBittorrent","quality":"WEBDL-1080p",
    "error":null,"added":"2026-11-23T15:40:00Z","web_url":"..."
  }],
  "activity": [{
    "key":"sonarr:9981","entry_id":"...","kind":"sonarr","event":"downloadFolderImported",
    "title":"Severance","subtitle":"S02E03 · Cold Harbor","date":"2026-11-23T15:12:00Z",
    "poster":"...","quality":"WEBDL-1080p","web_url":"..."
  }],
  "errors": [{"entry_id":"...","kind":"radarr","name":"Radarr","message":"Cannot connect"}]
}
```

Rules: `recent` and `queue` merged across servers then sorted `added` desc; `activity` sorted `date`
desc; `recent` limited to `recent_limit` **per server** before merging; all media `id` fields are ints;
`errors` lists only servers currently failing. `build_overview` must never include `api_key`,
`apiKey`, `apikey`, or `X-Api-Key` anywhere (test asserts this).

### 8.15 `http_views.py`

```python
class ArrOverviewView(HomeAssistantView):
    url = OVERVIEW_URL
    name = "api:arr_studio:overview"
    requires_auth = True
    async def get(self, request): ...

class ArrCoverView(HomeAssistantView):
    url = COVER_URL_TEMPLATE
    name = "api:arr_studio:cover"
    requires_auth = True
    async def get(self, request, entry_id, kind, media_id, variant): ...
```

- Overview: gather `entry.runtime_data` for all entries with `state is LOADED`; build payload; return
  `web.json_response(payload, headers={"Cache-Control": "no-store"})`.
- Cover: validate `kind in KINDS`, `variant in ALLOWED_VARIANTS`, `media_id` int > 0; find entry by
  `entry_id`; if `entry.runtime_data.client.kind != kind` → 404. Fetch bytes; on `ArrNotFoundError`
  → 404; on `ArrAuthError` → 403; on other `ArrError` → 502 with `{"error":"upstream"}`.
  Response headers: `Cache-Control: private, max-age=3600`,
  `Content-Type: image/jpeg`. Never cache 404s (`Cache-Control: no-store`).
- Register once in `async_setup` guarded by `hass.data[DATA_VIEWS_REGISTERED]`.

### 8.16 `frontend.py`

```python
async def async_register_frontend(hass: HomeAssistant) -> None
def async_remove_panel(hass: HomeAssistant) -> None
```

Registration (idempotent, guarded by `hass.data[DATA_FRONTEND_REGISTERED]`):

```python
files = Path(__file__).parent / "frontend"
await hass.http.async_register_static_paths(
    [StaticPathConfig(FRONTEND_STATIC_URL, str(files), True)]
)
version = await _async_version(hass)          # integration version via async_get_integration
frontend.async_register_built_in_panel(
    hass,
    component_name="custom",
    sidebar_title=PANEL_TITLE,
    sidebar_icon=PANEL_ICON,
    frontend_url_path=PANEL_URL_PATH,
    require_admin=False,
    config={"_panel_custom": {
        "name": PANEL_ELEMENT,
        "module_url": f"{FRONTEND_STATIC_URL}/{FRONTEND_ENTRY}?v={version}",
        "embed_iframe": False,
        "trust_external": False,
    }},
)
```
Check `"frontend" in hass.config.components` before registering; log a warning and continue without a
panel otherwise. Catch `ValueError`/`RuntimeError` for duplicate panel registration and treat as done.
`async_remove_panel` → `frontend.async_remove_panel(hass, PANEL_URL_PATH)` when the last entry unloads.

### 8.17 `__init__.py`

```python
async def async_setup(hass, config) -> bool:
    await async_register_frontend(hass)
    async_register_views(hass)
    await async_register_services(hass)
    hass.data.setdefault(DOMAIN, {})
    return True

async def async_setup_entry(hass, entry) -> bool:
    data = {**entry.data, **entry.options}
    client = ArrClient(hass, data[CONF_URL], data[CONF_API_KEY], data[CONF_KIND],
                       data.get(CONF_VERIFY_SSL, True))
    coordinator = ArrCoordinator(hass, entry, client, ...)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = ArrRuntimeData(client=client, coordinator=coordinator)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True

async def async_unload_entry(hass, entry) -> bool:
    ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if ok and not hass.config_entries.async_entries(DOMAIN):
        async_remove_panel(hass)
    return ok
```

Services: `arr_studio.refresh` with optional `entry_id`; if omitted refresh all. Use
`vol.Schema({vol.Optional("entry_id"): cv.string})`; schema registered once.

### 8.18 `diagnostics.py`

`async_get_config_entry_diagnostics` → 
```python
{"entry": {"title": e.title, "data": {**e.data, CONF_API_KEY: "**REDACTED**"},
           "options": e.options},
 "snapshot": {"kind":..., "online":..., "counts":..., "version":..., "queue_titles": [...]}}
```
No URLs with embedded credentials, no key fragments.

### 8.19 `scripts/preflight.py`

Argparse `--phase {0,1,2,3,5,6,7}`. Exit 1 on any failure, print `PASS`/`FAIL` lines. Checks:

1. Required files exist per phase (manifest, const, api, models, normalize, coordinator, config_flow,
   platforms, views, frontend files, brand PNGs, docs, tests, workflows).
2. `manifest.json` parses; required keys present; `domain == "arr_studio"`; `version` matches
   `const.VERSION` and (if tag present) git tag; `requirements == []`.
3. `hacs.json` parses and has `name`; `homeassistant` present.
4. `strings.json` and `translations/en.json` parse and are byte-identical.
5. Brand files: `icon.png` 256×256, `logo.png` 512×256 (PNG signature check; size via `struct`).
6. Python compile: `compileall` on `custom_components` and `scripts`.
7. Forbidden patterns in Python: `import requests`, `innerHTML`, `eval(`, `exec(`,
   `verify_ssl=False` hardcoded outside config flow, `apikey`/`api_key` in log calls.
8. Forbidden patterns in `custom_components/**/frontend/*.js` (except comments):
   `innerHTML`, `outerHTML`, `insertAdjacentHTML`, `eval(`, `new Function`, `document.write`,
   `http://`, `https://`, `api_key`, `apiKey`, `X-Api-Key`.
9. Grep tests: `payload.py`, `http_views.py`, `frontend/` must not reference `CONF_API_KEY`.
10. Entity key parity: the set of keys in `sensor.py` matches the table in `docs/PLAN.md` §8.10
    (implement a `SENSOR_KEYS` constant and compare a hard-coded tuple in the script).

### 8.20 `scripts/check_frontend.mjs`

Walk `custom_components/arr_studio/frontend/**/*.js`:
- run `node --check` equivalent via `new vm.SourceTextModule`? Simpler: spawn
  `node --input-type=module --check` per file using `child_process.execFileSync("node", ["--check", file])`
  (works for ES modules in Node ≥ 20 when file has `.js`? If not, use `--input-type=module` with stdin).
- regex scan for the forbidden patterns from §8.19 #8 and for unescaped interpolation inside
  `el(` calls? Not required — `el()` uses `textContent`.
- assert `panel.js` contains `customElements.define("arr-studio-panel"`.
- assert every `import ... from "./x.js"` target exists.
- assert total JS bytes < 400 KB.
- print `PASS frontend`.

---

## 9. Frontend specification (`arr-studio-panel`)

### 9.1 Module contracts

`api.js`
```js
export async function fetchOverview(hass)            // GET OVERVIEW_URL, no-store, returns object
export async function getCoverObjectUrl(hass, path)   // blobs, Map cache (max 200), returns url | null
export function lazyCover(hass, imgEl, path)          // IntersectionObserver -> getCoverObjectUrl
export function releaseCovers()                       // revoke all object URLs
```
Rules: `hass.fetchWithAuth(path, {cache: "no-store"})`; on non-OK throw `Error(status)`;
on 401 throw `Error("unauthorized")`. Cover cache keyed by `path`, max 200 entries, revoke oldest.

`format.js`
```js
export function fmtBytes(n)        // "4.8 GB", "812 MB"
export function fmtSpeed(bps)      // "12.4 MB/s", "—"
export function fmtEta(sec)        // "5m 12s", "1h 04m", "—"
export function fmtRelative(iso)   // "just now", "12m ago", "2d ago", date fallback
export function clamp01(n)
export function pct(n)             // 42
```

`dom.js`
```js
export function el(tag, props = {}, ...children)  // props: class, id, text, title, href, src,
                                                  // dataset, aria*, onClick, style (object)
export function svg(markup)                        // ONLY for trusted static icon strings
export function clear(node)
```
`el` never assigns `innerHTML`; text goes through `textContent`; attributes whitelisted.
`props.href` external links get `target="_blank" rel="noopener noreferrer"`.

`icons.js`: exports `ICONS = { film, download, clock, disk, check, alert, refresh, search, close,
sonarr, radarr }` — static SVG strings authored by us; no user data.

`state.js`
```js
export function loadState()   // {tab:"recent"|"downloads"|"activity", kind:"all"|"sonarr"|"radarr", sort:"newest"|"title"}
export function saveState(state)
```

`panel.js`
```js
class ArrStudioPanel extends HTMLElement {
  constructor()
  set hass(hass)          // first call mounts UI once, then re-renders if auth/theme changes
  set narrow(value)
  connectedCallback()     // start timer (30 s) + visibilitychange listener
  disconnectedCallback()  // clear timer, remove listener, releaseCovers()
  async _load(manual = false)
  _render()               // clears #root, rebuilds from this._data + this._state
  _onTab(tab) / _onKind(kind) / _onSort(sort) / _onQuery(q) / _openItem(item) / _closeDrawer()
}
customElements.define("arr-studio-panel", ArrStudioPanel);
```

Render states: `loading` (skeleton), `error` (full-page error with Retry), `empty` (no servers
configured → button linking to `/config/integrations/integration/arr_studio`), `data`.

### 9.2 Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│ topbar: [logo mark] Arr Studio        [● Live]  [search] [⟳]        │  sticky, blur
├─────────────────────────────────────────────────────────────────────┤
│ hero: blurred fanart + gradient                                     │
│   eyebrow ARR STUDIO · SONARR + RADARR                              │
│   h1  Your library, at a glance                                     │
│   pills: 128 titles | 3 downloading | 87 missing | disk ring 78%    │
│   server chips: ● Sonarr 4.0.15   ● Radarr 6.1.0                    │
├─────────────────────────────────────────────────────────────────────┤
│ tabs:  Recently added   |   Downloads   |   Activity      [sort ▾]  │
│ filters: All  Sonarr  Radarr                                        │
├─────────────────────────────────────────────────────────────────────┤
│ poster grid (auto-fill minmax(160px, 1fr), gap 18px)                │
│  [poster 2:3] [poster] [poster] [poster] [poster] [poster] ...      │
│  title / subtitle / NEW badge / kind dot                            │
├─────────────────────────────────────────────────────────────────────┤
│ footer: Updated 12s ago · Sonarr 4.0.15 · Radarr 6.1.0 · Refresh    │
└─────────────────────────────────────────────────────────────────────┘
```

Downloads tab: rows `[thumb 44×64] [title / subtitle / chips] [progress bar / speed / ETA]`.
Activity tab: compact rows `[thumb 36×54] [title / subtitle] [event label] [relative time]`.
Detail drawer: right-side sheet 480 px (full width on mobile) with fanart backdrop, poster, title,
year, meta chips, overview text, quality/size row, and `Open in Sonarr/Radarr` button.

### 9.3 Design tokens (`styles.js`)

```css
:host {
  --as-accent: var(--primary-color, #35c5f4);
  --as-sonarr: #35c5f4;
  --as-radarr: #ffc230;
  --as-radius: 18px;
  --as-radius-sm: 12px;
  --as-gap: 18px;
  --as-bg: var(--primary-background-color, #0b0f14);
  --as-card: var(--card-background-color, #151a21);
  --as-text: var(--primary-text-color, #f2f5f8);
  --as-muted: var(--secondary-text-color, #9aa4b2);
  --as-line: var(--divider-color, rgba(255,255,255,.10));
  --as-glass: rgba(255,255,255,.06);
  --as-elev: 0 18px 40px rgba(0,0,0,.38);
  --as-ease: cubic-bezier(.2,.8,.2,1);
  display: block; min-height: 100vh; color: var(--as-text);
  background:
    radial-gradient(1100px 520px at 12% -10%, rgba(53,197,244,.16), transparent 60%),
    radial-gradient(900px 460px at 92% -6%, rgba(255,194,48,.10), transparent 55%),
    var(--as-bg);
  font-family: var(--paper-font-body1_-_font-family, Roboto, system-ui, sans-serif);
  -webkit-font-smoothing: antialiased;
}
```

Hero: `border-radius: 26px; min-height: 210px; overflow: hidden; position: relative;`
backdrop image as `<div>` with `background-image`, `background-size: cover`, `filter: saturate(1.1)`,
overlay `linear-gradient(180deg, rgba(6,10,15,.25) 0%, rgba(6,10,15,.86) 100%)`.
Pills: `padding: 8px 14px; border-radius: 999px; background: var(--as-glass); border: 1px solid var(--as-line); backdrop-filter: blur(14px);`
Poster card:
```css
.poster { position: relative; border-radius: 14px; overflow: hidden; aspect-ratio: 2/3;
  background: linear-gradient(145deg,#1d242e,#0f141a); box-shadow: 0 12px 28px rgba(0,0,0,.35);
  transition: transform .35s var(--as-ease), box-shadow .35s var(--as-ease); }
.poster:hover { transform: translateY(-6px) scale(1.015); box-shadow: 0 22px 46px rgba(0,0,0,.5); }
.poster img { width: 100%; height: 100%; object-fit: cover; display: block; }
.poster .shade { position: absolute; inset: 0;
  background: linear-gradient(180deg, transparent 45%, rgba(4,7,10,.9) 100%); opacity: .0;
  transition: opacity .3s var(--as-ease); }
.poster:hover .shade { opacity: 1; }
```
NEW badge: `linear-gradient(135deg,#ffc230,#ff7a59)`, black text, 10 px uppercase, letter-spacing .08em.
Kind dot: 8 px circle, sonarr blue / radarr amber.
Progress: 6 px track, fill `linear-gradient(90deg, var(--as-accent), color-mix(in srgb, var(--as-accent), white 35%))`, animated width.
Skeleton: `background: linear-gradient(90deg, rgba(255,255,255,.05), rgba(255,255,255,.12), rgba(255,255,255,.05)); background-size: 200% 100%; animation: shimmer 1.4s infinite;`
Entrance: `@keyframes rise { from { opacity:0; transform: translateY(14px) } to { opacity:1; transform:none } }`, per-card `animation-delay: calc(var(--i, 0) * 38ms)`.
Reduced motion: `@media (prefers-reduced-motion: reduce) { *, *::before, *::after { animation: none !important; transition: none !important; } }`

Responsive breakpoints: ≤ 720 px → hero 170 px, grid 2 columns, queue rows stack ETA below bar,
drawer full width; ≤ 430 px → grid 2 columns with 12 px gap, tabs horizontally scrollable.

Accessibility: tabs are `<button role="tab" aria-selected>`; cards are `<button class="tile">` with
`aria-label="{title}, {subtitle}"`; focus ring `outline: 2px solid var(--as-accent); outline-offset: 3px`;
refresh toast `role="status" aria-live="polite"`; images `alt=""` (decorative, title is adjacent) or
`alt="{title} poster"` in drawer.

### 9.4 Frontend behavioural rules

- **Newest first**: `recent` is pre-sorted by the backend; the panel must not re-sort by title unless
  the user picks `sort=title`.
- Cover loading: create `<img>` with the placeholder as `src` first, then swap to the blob URL when
  ready; on error keep placeholder (no broken-image icon).
- **Lazy covers:** only fetch a cover when its tile is within 200 px of the viewport
  (`IntersectionObserver`, one observer per render, disconnected on re-render). Live posters are up to
  1.3 MB, so eager loading is not acceptable. Cache blob URLs (max 200) and reuse them across tabs.
- Polling: 30 s; skip when `document.hidden`; immediate reload on `visibilitychange` → visible.
- Manual refresh: calls `hass.callService("arr_studio", "refresh", {})`, shows spinner for ≤ 3 s, then reloads.
- Search: client-side filter on `title` + `subtitle`, case-insensitive, debounce 150 ms.
- Empty tab states have a short hint, not a spinner.
- No `alert()`, no `console.log` in production code (console.error allowed in catch blocks).
- All user-visible strings in English (v0.1); no i18n layer in JS.

---

## 10. Entity catalogue (one configured server)

| Entity ID pattern | Platform | Key | Notes |
|---|---|---|---|
| `sensor.<title>_queue` | sensor | `queue` | count |
| `sensor.<title>_downloading` | sensor | `downloading` | count + `speed` attr |
| `sensor.<title>_recent_additions` | sensor | `recent` | count + `latest_title` |
| `sensor.<title>_library` | sensor | `library` | count + `size_gb` |
| `sensor.<title>_missing` | sensor | `missing` | count |
| `sensor.<title>_disk_free` | sensor | `disk_free` | GiB |
| `sensor.<title>_health_issues` | sensor | `health` | count |
| `binary_sensor.<title>_online` | binary_sensor | `online` | connectivity |
| `image.<title>_latest_poster` | image | `latest_poster` | thumbnail |
| `button.<title>_refresh` | button | `refresh` | forces poll |

With both servers configured: 20 entities, 2 devices, 1 panel.

---

## 11. Security & privacy requirements

1. API key lives only in the config entry and in `ArrClient` request headers.
2. `ArrCoverView` and `ArrOverviewView` have `requires_auth = True`; unauthenticated requests → 401.
3. No key, key fragment, or `?apikey=` URL in: payload JSON, HTML, JS, logs, diagnostics, exceptions,
   entity attributes, device info, panel URLs.
4. Cover view validates path params against allowlists before any network call (SSRF guard).
5. Media titles/overviews are inserted via `textContent` only; no HTML injection path.
6. External links use `rel="noopener noreferrer"`.
7. `verify_ssl` is user-configurable but defaults to `True`; preflight forbids hardcoded `False`.
8. Diagnostics redact `api_key`; error messages are constructed from status codes, not response bodies.
9. Do not log response bodies at any level.

---

## 12. Testing & CI

### 12.1 Python tests (no HA install required for required tests)

- `conftest.py`: load fixtures as JSON; helper `sonarr_series()`, etc.
- `test_api.py`: spin an `aiohttp` test server on `127.0.0.1:0` with routes for status/queue/cover;
  assert:
  - `normalize_base_url` cases (`http://x:8989/`, `x:8989`, `http://x/api/v3`, with spaces).
  - Header sent is `X-Api-Key`.
  - 401 → `ArrAuthError`; 500 → `ArrResponseError`; connection refused → `ArrConnectionError`;
    `/mediacover/...` 404 → `None`.
  - `async_validate` rejects a Sonarr URL configured as Radarr (`wrong_server` path).
- `test_normalize.py`: fixture-driven; assert poster paths, subtitles, progress clamp
  (`size=0` → `None`, negative → `0.0`, >size → `1.0`), `parse_timeleft("1.02:03:04") == 93784`,
  `normalize_history` returns `None` for unknown/irrelevant events, missing counts skip unmonitored
  when `show_unmonitored=False`, `iso_utc` normalises `Z`.
- `test_payload.py`: two fake runtimes (sonarr+radarr); assert merged `recent` sorted desc, limit per
  server, `errors` populated for offline, JSON has no `api_key`/`apikey` (case-insensitive) and every
  `poster` starts with `/api/arr_studio/cover/`.
- `test_format.py`: `compute_progress`, `fmt` helpers if shared? (Python-side only for
  `compute_progress`/`parse_timeleft`; JS formatting is checked by node script only.)

### 12.2 Frontend checks

`node scripts/check_frontend.mjs` — syntax + forbidden patterns + import graph + size.

### 12.3 CI — `.github/workflows/validate.yml`

```yaml
name: Validate
on:
  push:
  pull_request:
jobs:
  python:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: "3.13"}
      - run: pip install ruff pytest aiohttp pyyaml
      - run: ruff check .
      - run: python scripts/preflight.py --phase 6
      - run: pytest -q
  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: {node-version: "22"}
      - run: node scripts/check_frontend.mjs
  hassfest:
    uses: home-assistant/actions/.github/workflows/hassfest.yaml@master
  hacs:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: hacs/action@main
        with: {category: integration}
```

### 12.4 Manual HA verification (dev harness)

See §13. Required passes before tagging:

1. Config flow happy path for both kinds; invalid key shows `invalid_auth`; wrong server shows
   `wrong_server`; duplicate URL aborts.
2. Options change (scan interval 15 s) reloads and polling speeds up.
3. Stop mock server → `binary_sensor.*_online` off, panel error banner, log has one warning per poll max.
4. Restart mock with a new queue item → it appears within one interval; when it completes, it moves to
   Activity.
5. Delete the entry → entities removed, panel removed after the last entry.
6. `curl` overview unauthenticated → 401; authenticated → valid JSON with no key.
7. `python3 scripts/live_smoke.py` passes against the human's real servers (verified 2026-11-23:
   Sonarr 4.0.20.3014 and Radarr 7.0.3.10918, both HTTP on the LAN). Re-run it after any change to
   `api.py` or `normalize.py`; the queue was empty on that date, so also watch for a real download to
   confirm queue fields end-to-end.

---

## 13. Dev harness (`dev/`)

```
dev/
├─ Dockerfile.mock
├─ docker-compose.yml
├─ mock_arr.py
└─ config/configuration.yaml
```

`mock_arr.py`: stdlib `http.server` (no deps) or `aiohttp`; CLI `--kind sonarr|radarr --port 8989
--fixtures ../tests/fixtures`; serves `/api/v3/system/status`, `/health`, `/diskspace`, `/queue`,
`/history`, `/series` or `/movie`, `/calendar`, `/mediacover/{id}/{variant}.jpg` (returns a generated
SVG with the title, `Content-Type: image/svg+xml`), ignores auth header but returns 401 when
`X-Api-Key` is missing. Supports `--fault 401|500|timeout` env to exercise error paths.

`docker-compose.yml`:
```yaml
services:
  homeassistant:
    image: ghcr.io/home-assistant/home-assistant:stable
    ports: ["8123:8123"]
    volumes:
      - ./config:/config
      - ../custom_components:/config/custom_components
    environment: {TZ: Europe/London}
  sonarr:
    build: {context: ., dockerfile: Dockerfile.mock}
    command: ["python", "mock_arr.py", "--kind", "sonarr", "--port", "8989"]
    volumes: ["../tests/fixtures:/fixtures:ro"]
  radarr:
    build: {context: ., dockerfile: Dockerfile.mock}
    command: ["python", "mock_arr.py", "--kind", "radarr", "--port", "7878"]
    volumes: ["../tests/fixtures:/fixtures:ro"]
```

`docs/TESTING.md` documents: `docker compose up --build`, onboarding, adding `http://sonarr:8989`
key `test`, screenshot commands, and how to seed "recent" items by editing fixtures.

### 13.1 Live credential validation (`scripts/live_smoke.py`)

The human stores real credentials in `.env` (repo root, git-ignored):

```
SONARR_URL=http://192.168.1.10:8989
SONARR_API_KEY=...
RADARR_URL=http://192.168.1.10:7878
RADARR_API_KEY=...
```

`scripts/live_smoke.py` (stdlib only) reads `.env`, then for each configured server verifies and
prints without ever echoing the key. It accepts both the documented `KEY=VALUE` form and a plain
notes form:

```
Radarr:
url=http://192.168.1.10:7878
API key=...

Sonarr:
url=http://192.168.1.10:8989
API key=...
```

`url`/`host` and `api key`/`api_key`/`apikey` are matched case-insensitively inside a
`Sonarr`/`Radarr` section. Displayed URLs have credentials and query strings stripped.

1. `GET /api/v3/system/status` — appName/version/instanceName, and that appName matches the kind.
2. `GET /api/v3/health` — issue count and types.
3. `GET /api/v3/diskspace` — largest volume free/total.
4. `GET /api/v3/queue` with the exact params from §4.1 — record count, presence of
   `size`/`sizeleft`/`timeleft`/`status`/`protocol`/`downloadClient`, and a sample progress line.
5. `GET /api/v3/series|movie` — count and the 3 newest items by `added`, including which
   `coverType` values exist.
6. `GET /api/v3/mediacover/{id}/poster.jpg` — HTTP status, content type, byte size (proves the
   proxied-thumbnail approach works on the real server).
7. `GET /api/v3/history` — record count and distinct `eventType` values.
8. `GET /api/v3/calendar` for the next 14 days — count.

Exit code 0 only when every configured server passes; a missing credential pair is reported as
"skipped", not failed. Flags: `--only sonarr|radarr`, `--insecure` (self-signed TLS), `--env PATH`.

Run it **before Phase 1** and again after Phase 4: it confirms the field names this plan relies on
(especially `sizeleft`, `timeleft`, `trackedDownloadState`, `images[].coverType`, and the
`/mediacover` route) against the human's actual Sonarr/Radarr versions. If a field is absent,
record it in `docs/TESTING.md` and adapt `normalize.py` — do not guess.

---

## 14. Acceptance criteria (definition of done)

- [ ] Marketplace (2026.11+) install from a custom repo: `github.com/etanyxyz/Arr-Studio` succeeds, panel appears after restart, no manual YAML.
- [ ] Both Sonarr and Radarr entries can coexist; all 20 entities exist, unique IDs stable across reloads.
- [ ] Panel: hero, stat pills, poster grid, downloads, activity, filters, sort, search, detail drawer all work; newest items first; covers visible.
- [ ] Any configured server offline → online sensor off, panel shows per-server error, other server unaffected.
- [ ] Auth failure triggers reauth in HA UI; recovering the key restores entities without restart.
- [ ] No API key anywhere in browser-visible output (`grep -ri "apikey\|api_key" custom_components/arr_studio/frontend` returns nothing; payload test passes).
- [ ] Mobile 390 px and desktop 1440 px layouts; light and dark HA themes legible.
- [ ] `scripts/live_smoke.py` passes against the human's real Sonarr and Radarr from `.env`.
- [ ] `ruff check .`, `pytest -q`, `node scripts/check_frontend.mjs`, hassfest, HACS Action all green.
- [ ] Manifest version == git tag == HACS release; brand icon/logo present.
- [ ] README has screenshots, install steps, entity table, troubleshooting.

---

## 15. Post-v0.1 roadmap (do not implement yet)

1. Lovelace card `custom:arr-studio-card` using the same render modules, registered as a Lovelace
   resource (storage mode) from the integration, with a documented manual fallback for YAML mode.
2. Dashboard strategy `custom:arr-studio` (needs HA ≥ 2026.5, `window.customStrategies` +
   `ll-strategy-dashboard-arr-studio`), only offered once the resource is confirmed loaded.
3. Calendar sensor per server with next-episode attributes (bounded, 5 items).
4. `media_player`-style "now downloading" entity? Rejected — not a media player; keep sensors.
5. Optional commands (search missing, retry failed) behind explicit user confirmation.
6. Translations (de, fr, nl, es) via `translations/*.json`.

---

## 16. Risks and mitigations

| Risk | Mitigation |
|---|---|
| HA API drift (`async_register_static_paths`, panel registration) | Pinned minimum 2025.6; CI hassfest; all calls in `frontend.py` with try/except + warning |
| Cover endpoint 404 because Arr hasn't cached artwork | Fallback chain: proxy API → `images[].remoteUrl` (client-side `<img>` upload? no) → bundled placeholder |
| Large libraries slow polling | Library cached 10 min, queue capped at 100 records, recent limited to 12/server |
| TimeSpan parsing differences | Prefer `estimatedCompletionTime`; regex fallback; ETA is optional (`—`) |
| Panel not loading (module 404) | Preflight verifies file names + import graph; screenshot test; version query on module URL |
| Small model writes XSS-able DOM code | `el()`-only rule + `innerHTML` forbidden by preflight |
| Key leakage | Key confined to `api.py`; preflight grep; payload test; cover view allowlist |
| Recorder bloat | No list attributes on entities; lists only via HTTP |

---

## 17. Local model workflow (per phase)

1. `git pull --rebase`
2. Read this plan section for the phase (do not read the whole file every time).
3. Implement files exactly as specified.
4. Run the phase checkpoint; copy command output into the commit body if it fails once and then passes.
5. `git add -A && git commit -m "<message from §7>"`
6. `git push origin main`
7. Report: phase, files touched, checkpoint result, open questions.

If a spec is ambiguous: **stop and ask**, do not improvise. If a test fails: fix code, never tests,
unless the test contradicts this plan (then ask).

---

## 18. Decisions (resolved)

1. **Panel-first is approved.** The v0.1.0 showcase is the `arr-studio` sidebar panel; a Lovelace
   card and a dashboard strategy are deferred to v0.2 (§15).
2. **Branding approved:** name `Arr Studio`, domain `arr_studio`, Sonarr blue `#35c5f4` and Radarr
   amber `#ffc230` accents.
3. **Live servers available.** The human keeps real URLs and API keys in a git-ignored `.env` in the
   repository root. `.env.example` documents the four keys; `scripts/live_smoke.py` validates them.
   Never commit, print, copy or read `.env` into the integration; the integration is configured
   through the HA UI. Preflight enforces `.env` being ignored and untracked.
4. **Licence:** MIT, copyright 2026 etanyxyz, plus the "not affiliated with Sonarr, Radarr or Home
   Assistant" disclaimer in `README.md`.