"""Tests for the Arr Studio payload building."""


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
