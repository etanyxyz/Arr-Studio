"""pytest configuration for the Arr Studio integration tests.

Fixture JSON loaders (plan §12.1): `load_fixture("sonarr_series.json")` plus
one helper per fixture file.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def load_fixture(name: str) -> Any:
    """Load a JSON fixture from tests/fixtures/ by file name."""
    with (FIXTURES_DIR / name).open(encoding="utf-8") as handle:
        return json.load(handle)


def sonarr_series() -> list[dict]:
    """Sonarr /api/v3/series library fixture."""
    return load_fixture("sonarr_series.json")


def sonarr_queue() -> list[dict]:
    """Sonarr /api/v3/queue records fixture."""
    return load_fixture("sonarr_queue.json")


def sonarr_history() -> list[dict]:
    """Sonarr /api/v3/history records fixture."""
    return load_fixture("sonarr_history.json")


def sonarr_diskspace() -> list[dict]:
    """Sonarr /api/v3/diskspace fixture."""
    return load_fixture("sonarr_diskspace.json")


def sonarr_status() -> dict:
    """Sonarr /api/v3/system/status fixture."""
    return load_fixture("sonarr_status.json")


def radarr_movie() -> list[dict]:
    """Radarr /api/v3/movie library fixture."""
    return load_fixture("radarr_movie.json")


def radarr_queue() -> list[dict]:
    """Radarr /api/v3/queue records fixture."""
    return load_fixture("radarr_queue.json")


def radarr_history() -> list[dict]:
    """Radarr /api/v3/history records fixture."""
    return load_fixture("radarr_history.json")
