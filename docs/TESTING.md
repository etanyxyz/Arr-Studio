# Arr Studio Testing

Testing is layered: unit tests for the API client and normalisation, a payload
contract test for the panel API, a per-phase preflight gate, and optional live
smoke checks against real servers.

## Test suite

- `tests/test_api.py` — `ArrClient` URL/argument normalisation, header
  handling, status raising, cover fetching, and validation, with an
  `aiohttp` test server.
- `tests/test_normalize.py` — every pure function in `normalize.py`
  (`cover_path`, `pick_image`, `iso_utc`, `compute_progress`, `parse_timeleft`,
  `parse_datetime`, `normalize_series`, `normalize_movie`, `normalize_queue`,
  `normalize_history`, `normalize_health`, `normalize_disks`,
  `compute_missing`, `merge_counts`, `web_url`, `sort_newest_first`) against
  captured live fixtures in `tests/fixtures/`.
- `tests/test_payload.py` — the overview payload contract from plan §8.14:
  exact key set, `key` of `f"{kind}:{id}"` on every item, merged and sorted
  lists, per-server recent limit, error surfacing, and no credential tokens
  anywhere in the serialized payload.

Fixtures are captured responses from live instances:

- Sonarr 4.0.20.3014: series, queue, history, status, diskspace
- Radarr 7.0.3.10918: movies, queue, history, status, diskspace

## Running

The development venv (Python 3.12, `homeassistant 2025.1.4`, `pytest`,
`pytest-asyncio`, `ruff`) is created at the repo root:

```bash
.venv/bin/pytest tests -q
.venv/bin/ruff check .
```

`pytest -q` works from a plain venv too, since `pyproject.toml` sets
`pythonpath = ["."]`.

## Preflight

`scripts/preflight.py --phase N` runs the phase gate: required files,
manifest/hacs consistency, forbidden Python and JavaScript patterns,
translations equality, payload key contract (phase 4+), sensor key parity
(phase 3+) and brand PNG checks (phase 5+). Each phase section in
`docs/PLAN.md` names the phase number its checkpoint uses.

## Live smoke (optional)

`scripts/live_smoke.py` exercises a real Sonarr and Radarr with credentials
read from a git-ignored `.env` (copy `.env.example` to `.env` first). It is
not part of the automated checkpoints and never touches the test suite.

```bash
cp .env.example .env    # then fill in URLs and API keys
.venv/bin/python scripts/live_smoke.py
```

## CI

`.github/workflows/validate.yml` runs on every push and pull request:

- `validate` — `ruff check .`, `pytest -q`, `node scripts/check_frontend.mjs`
- `hassfest` — manifest and strings validation
- `hacs` — HACS repository validation via `hacs/action`

## Phase checkpoints

Each phase in `docs/PLAN.md` ends with an explicit checkpoint command block
(preflight + pytest +, where applicable, the frontend check or a live curl).
A phase is only committed when its checkpoint passes.
