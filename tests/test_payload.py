"""Tests for the Arr Studio payload building."""

from __future__ import annotations

from types import SimpleNamespace

from custom_components.arr_studio.payload import build_overview


def test_build_overview_empty():
    """Build overview with no runtimes."""
    result = build_overview([], 12)
    assert result["version"] == 1
    assert result["generated_at"] == "2026-11-23T16:00:00+00:00"
    assert result["servers"] == []
    assert result["recent"] == []
    assert result["queue"] == []
    assert result["activity"] == []
    assert result["errors"] == []


def test_build_overview_single_server():
    """Build overview with one server."""
    class FakeClient:
        _kind = "sonarr"
        _base_url = "http://test.local"

    class FakeEntry:
        entry_id = "sonarr-1"
        runtime_data = None

    class FakeSnapshot:
        counts = {"queue": 0, "downloading": 0, "recent": 0, "library": 0, "missing": 0, "upcoming": 0, "health": 0}
        disk = None
        speed_bps = 0

    runtimes = [FakeClient()]
    result = build_overview(runtimes, 12)
    assert len(result["servers"]) == 1
    assert result["servers"][0]["entry_id"] == "sonarr-1"
    assert result["servers"][0]["kind"] == "sonarr"
    assert result["servers"][0]["online"] is True
    assert result["servers"][0]["error"] is None
    assert result["servers"][0]["counts"] == {"queue": 0, "downloading": 0, "recent": 0, "library": 0, "missing": 0, "upcoming": 0, "health": 0}


def test_build_overview_multiple_servers():
    """Build overview with multiple servers."""
    class FakeClient:
        _kind = "sonarr"
        _base_url = "http://test.local"

    runtimes = [FakeClient(), FakeClient()]
    result = build_overview(runtimes, 12)
    assert len(result["servers"]) == 2
    assert result["servers"][0]["entry_id"] == "sonarr-1"
    assert result["servers"][1]["entry_id"] == "sonarr-2"


def test_build_overview_no_api_key():
    """Ensure api_key is not in the overview payload."""
    class FakeClient:
        _kind = "sonarr"
        _base_url = "http://test.local"

    runtimes = [FakeClient()]
    result = build_overview(runtimes, 12)
    # Verify no api_key in the output
    assert "api_key" not in str(result)
    assert "apiKey" not in str(result)
    assert "apikey" not in str(result)


def _full_snapshot():
    """Snapshot with every field the payload reads for a coordinator-backed server."""
    return SimpleNamespace(
        name="Sonarr",
        version="99.9.9",
        online=True,
        error=None,
        disk=None,
        speed_bps=0,
        recent=(),
        queue=(),
        activity=(),
        counts={"queue": 0, "downloading": 0, "recent": 0, "library": 0, "missing": 0, "upcoming": 0, "health": 0},
    )


def _runtime(last_update_success: bool, last_exception: Exception | None) -> SimpleNamespace:
    """ArrRuntimeData-shaped fake: client plus coordinator state."""
    client = SimpleNamespace(kind="sonarr", base_url="http://offline.local")
    coordinator = SimpleNamespace(
        config_entry=SimpleNamespace(entry_id="sonarr-1"),
        data=_full_snapshot(),
        last_update_success=last_update_success,
        last_exception=last_exception,
    )
    return SimpleNamespace(client=client, coordinator=coordinator)


def test_offline_server_shows_error():
    """Plan §14: failing server -> online=false, per-server error and a
    populated errors list for the panel banner."""
    failure = Exception("Cannot connect: Connection refused")
    result = build_overview([_runtime(False, failure)], 12)
    server = result["servers"][0]
    assert server["online"] is False
    assert server["error"] == "Cannot connect: Connection refused"
    assert result["errors"] == [
        {
            "entry_id": "sonarr-1",
            "kind": "sonarr",
            "name": "Sonarr",
            "message": "Cannot connect: Connection refused",
        }
    ]


def test_recovered_server_no_stale_error():
    """HA never clears last_exception on a successful refresh; the payload
    must not report stale errors once the server recovers."""
    result = build_overview(
        [_runtime(True, Exception("Cannot connect: Connection refused"))], 12
    )
    server = result["servers"][0]
    assert server["online"] is True
    assert server["error"] is None
    assert result["errors"] == []
