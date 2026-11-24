"""Test the Arr API client."""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.arr_studio.api import (
    ArrAuthError,
    ArrClient,
    ArrConnectionError,
    ArrNotFoundError,
    ArrResponseError,
)


class TestArrClient:
    """Tests for ArrClient."""

    @pytest.fixture
    def client(self):
        """Return a real ArrClient with a mocked HTTP session."""
        return self._make_client()

    def _make_client(self):
        """Return a real ArrClient instance (or mock its session)."""
        # We'll use a real client but mock the HTTP calls
        client = ArrClient(
            hass=MagicMock(),
            base_url="http://test.local",
            api_key="test-key",
            kind="sonarr",
            verify_ssl=True,
        )
        client._session = MagicMock()
        client._session.get = AsyncMock()
        client._session.get.return_value.status = 200
        client._session.get.return_value.json = AsyncMock(return_value={})
        return client

    def _json_response(self, payload, status=200):
        """Return a mock HTTP response with a JSON payload."""
        resp = MagicMock()
        resp.status = status
        resp.json = AsyncMock(return_value=payload)
        return resp

    async def test_get_status(self, client):
        """GET /api/v3/system/status returns a dict."""
        client._session.get = AsyncMock(return_value=self._json_response({"appName": "Sonarr"}))
        result = await client.async_get_status()
        assert isinstance(result, dict)

    async def test_get_health(self, client):
        """GET /api/v3/health returns a list."""
        client._session.get = AsyncMock(
            return_value=self._json_response([{"source": "s", "type": "warning", "message": "m"}])
        )
        result = await client.async_get_health()
        assert isinstance(result, list)

    async def test_get_diskspace(self, client):
        """GET /api/v3/diskspace returns a list."""
        client._session.get = AsyncMock(
            return_value=self._json_response([{"path": "/tv", "freeSpace": 1, "totalSpace": 2}])
        )
        result = await client.async_get_diskspace()
        assert isinstance(result, list)

    async def test_get_queue(self, client):
        """GET /api/v3/queue returns a list."""
        client._session.get = AsyncMock(return_value=self._json_response([{"id": 1, "title": "release"}]))
        result = await client.async_get_queue(page_size=100)
        assert isinstance(result, list)

    async def test_get_history(self, client):
        """GET /api/v3/history returns a list."""
        client._session.get = AsyncMock(
            return_value=self._json_response([{"id": 1, "eventType": "grabbed", "sourceTitle": "release"}])
        )
        result = await client.async_get_history(page_size=20)
        assert isinstance(result, list)

    async def test_get_library(self, client):
        """GET /api/v3/series or /api/v3/movie returns a list."""
        client._session.get = AsyncMock(return_value=self._json_response([{"id": 1, "title": "series"}]))
        result = await client.async_get_library()
        assert isinstance(result, list)

    async def test_get_calendar(self, client):
        """GET /api/v3/calendar returns a list."""
        client._session.get = AsyncMock(return_value=self._json_response([{"id": 1, "title": "series"}]))
        result = await client.async_get_calendar(days=14)
        assert isinstance(result, list)

    async def test_get_cover_404(self, client):
        """GET a missing cover returns None."""
        resp = MagicMock()
        resp.status = 404
        client._session.get = AsyncMock(return_value=resp)
        result = await client.async_get_cover(media_id=1, variant="poster")
        assert result is None

    async def test_get_cover_502(self, client):
        """GET a non-200 response raises ArrResponseError."""
        resp = MagicMock()
        resp.status = 502
        client._session.get = AsyncMock(return_value=resp)
        with pytest.raises(ArrResponseError):
            await client.async_get_cover(media_id=1, variant="poster")

    async def test_validate_wrong_app(self):
        """validate() raises ArrResponseError when appName doesn't match kind."""
        client = ArrClient(
            hass=MagicMock(),
            base_url="http://test.local",
            api_key="test-key",
            kind="sonarr",
            verify_ssl=True,
        )
        client._session = MagicMock()
        client._session.get = AsyncMock(return_value=self._json_response({
            "appName": "Radarr",
            "instanceName": "Radarr",
            "version": "7.0.3",
            "startTime": "2026-11-23T12:00:00Z",
            "osName": "Linux",
        }))
        with pytest.raises(ArrResponseError):
            await client.async_validate()

    async def test_validate_success(self):
        """validate() returns status when appName matches kind."""
        client = ArrClient(
            hass=MagicMock(),
            base_url="http://test.local",
            api_key="test-key",
            kind="sonarr",
            verify_ssl=True,
        )
        client._session = MagicMock()
        client._session.get = AsyncMock(return_value=self._json_response({
            "appName": "Sonarr",
            "instanceName": "Sonarr",
            "version": "4.0.20.3014",
            "startTime": "2026-11-23T12:00:00Z",
            "osName": "Linux",
        }))
        result = await client.async_validate()
        assert result["appName"] == "Sonarr"

    async def test_normalize_base_url(self):
        """normalize_base_url strips trailing slash and /api/v3 suffixes."""
        assert ArrClient.normalize_base_url("http://test.local/") == "http://test.local"
        assert ArrClient.normalize_base_url("http://test.local/api/v3") == "http://test.local"
        assert ArrClient.normalize_base_url("http://test.local/api") == "http://test.local"

    async def test_normalize_api_key(self):
        """normalize_api_key strips whitespace and newlines."""
        assert ArrClient.normalize_api_key("  key  \n  ") == "key"

    async def test_normalize_url(self):
        """normalize_base_url handles various URL forms."""
        assert ArrClient.normalize_base_url("https://example.com") == "https://example.com"
        assert ArrClient.normalize_base_url("https://example.com/") == "https://example.com"
        assert ArrClient.normalize_base_url("https://example.com/api/v3") == "https://example.com"

    async def test_normalize_base_url_no_trailing(self):
        """normalize_base_url works with no trailing slash."""
        assert ArrClient.normalize_base_url("http://test.local") == "http://test.local"

    async def test_normalize_url_no_trailing(self):
        """normalize_base_url handles URLs with no trailing slash."""
        assert ArrClient.normalize_base_url("https://example.com") == "https://example.com"

    async def test_normalize_headers(self):
        """Headers are set correctly on the client."""
        client = ArrClient(
            hass=MagicMock(),
            base_url="http://test.local",
            api_key="test-key",
            kind="sonarr",
            verify_ssl=True,
        )
        client._session = MagicMock()
        client._session.get = AsyncMock()
        client._session.get.return_value.status = 200
        client._session.get.return_value.json = AsyncMock(return_value={})
        # Verify headers are correct by checking the _headers method
        assert client._headers() == {
            "X-Api-Key": "test-key",
            "Accept": "application/json",
        }

    async def test_normalize_cover_headers(self):
        """Cover request uses different headers (image/*, */*)."""
        client = ArrClient(
            hass=MagicMock(),
            base_url="http://test.local",
            api_key="test-key",
            kind="sonarr",
            verify_ssl=True,
        )
        client._session = MagicMock()
        client._session.get = AsyncMock()
        client._session.get.return_value.status = 200
        client._session.get.return_value.json = AsyncMock(return_value={})
        assert client._cover_headers() == {
            "X-Api-Key": "test-key",
            "Accept": "image/*, */*",
        }

    async def test_normalize_close(self):
        """close() shuts down the session."""
        client = ArrClient(
            hass=MagicMock(),
            base_url="http://test.local",
            api_key="test-key",
            kind="sonarr",
            verify_ssl=True,
        )
        client._session = MagicMock()
        await client.close()

    async def test_normalize_error(self):
        """ArrConnectionError is raised on connection failures."""
        client = ArrClient(
            hass=MagicMock(),
            base_url="http://test.local",
            api_key="test-key",
            kind="sonarr",
            verify_ssl=True,
        )
        client._session = MagicMock()
        client._session.get = AsyncMock(side_effect=asyncio.TimeoutError())
        with pytest.raises(ArrConnectionError):
            await client.async_get_status()

    async def test_normalize_auth_error(self):
        """ArrAuthError is raised on 401/403."""
        client = ArrClient(
            hass=MagicMock(),
            base_url="http://test.local",
            api_key="test-key",
            kind="sonarr",
            verify_ssl=True,
        )
        resp = MagicMock()
        resp.status = 403
        client._session = MagicMock()
        client._session.get = AsyncMock(return_value=resp)
        with pytest.raises(ArrAuthError):
            await client.async_get_status()

    async def test_normalize_not_found(self):
        """ArrNotFoundError is raised on 404."""
        client = ArrClient(
            hass=MagicMock(),
            base_url="http://test.local",
            api_key="test-key",
            kind="sonarr",
            verify_ssl=True,
        )
        # Cover 404 returns None per plan §8.4 (see test_get_cover_404); the
        # 404 -> ArrNotFoundError mapping is covered through a JSON endpoint.
        resp = MagicMock()
        resp.status = 404
        client._session = MagicMock()
        client._session.get = AsyncMock(return_value=resp)
        with pytest.raises(ArrNotFoundError):
            await client.async_get_status()

    async def test_normalize_response_error(self):
        """ArrResponseError is raised on 4xx other than 401/403/404."""
        client = ArrClient(
            hass=MagicMock(),
            base_url="http://test.local",
            api_key="test-key",
            kind="sonarr",
            verify_ssl=True,
        )
        resp = MagicMock()
        resp.status = 500
        client._session = MagicMock()
        client._session.get = AsyncMock(return_value=resp)
        with pytest.raises(ArrResponseError):
            await client.async_get_status()
