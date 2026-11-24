"""Regression tests for the ArrLatestPosterImage entity (plan §8.12).

Covers the HA 2026.x ImageEntity contract: access_tokens must exist before
the first state write, and async_image must return bytes (content type via
_attr_content_type), never a (bytes, content_type) tuple.
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

from custom_components.arr_studio.api import ArrConnectionError
from custom_components.arr_studio.const import KIND_SONARR
from custom_components.arr_studio.image import ArrLatestPosterImage
from custom_components.arr_studio.models import MediaItem, ServerSnapshot


def _snapshot() -> ServerSnapshot:
    """A snapshot with one recent item."""
    return ServerSnapshot(
        entry_id="entry-1",
        kind=KIND_SONARR,
        name="Sonarr",
        version="4.0.20",
        online=True,
        error=None,
        library=(),
        recent=(
            MediaItem(
                entry_id="entry-1",
                kind=KIND_SONARR,
                id=42,
                title="The Test Show",
            ),
        ),
        queue=(),
        activity=(),
        disk=None,
        counts={},
    )


def _empty_snapshot() -> ServerSnapshot:
    """A snapshot with no recent items."""
    return ServerSnapshot(
        entry_id="entry-1",
        kind=KIND_SONARR,
        name="Sonarr",
        version="4.0.20",
        online=True,
        error=None,
        library=(),
        recent=(),
        queue=(),
        activity=(),
        disk=None,
        counts={},
    )


def _entity(snapshot: ServerSnapshot | None) -> ArrLatestPosterImage:
    """Build an image entity backed by a stub coordinator and hass."""
    coordinator = MagicMock()
    entry = MagicMock()
    entry.entry_id = "entry-1"
    entry.title = "Sonarr"
    coordinator.config_entry = entry
    coordinator.data = snapshot
    entity = ArrLatestPosterImage(coordinator)

    async def _job(func, *args):
        return func(*args)

    entity.hass = MagicMock()
    entity.hass.async_add_executor_job = _job
    return entity


def test_added_to_hass_initializes_access_tokens() -> None:
    """async_added_to_hass must run ImageEntity.__init__ so access_tokens
    exists before the first state write (regression: AttributeError
    'ArrLatestPosterImage' object has no attribute 'access_tokens')."""
    entity = _entity(_snapshot())
    entity.hass = MagicMock()
    asyncio.run(entity.async_added_to_hass())
    assert len(entity.access_tokens) == 1


def test_async_image_returns_bytes_with_content_type() -> None:
    """async_image returns raw bytes; the content type goes to
    _attr_content_type (the 2026.x image view reads them separately)."""
    entity = _entity(_snapshot())

    async def fake_cover(media_id: int, variant: str = "poster") -> tuple[bytes, str]:
        return (b"jpeg-bytes", "image/jpeg")

    entity.coordinator.client.async_get_cover = fake_cover
    result = asyncio.run(entity.async_image())
    assert result == b"jpeg-bytes"
    assert entity._attr_content_type == "image/jpeg"


def test_async_image_falls_back_to_placeholder() -> None:
    """A failed cover fetch serves the bundled placeholder instead."""
    entity = _entity(_snapshot())

    async def failing_cover(media_id: int, variant: str = "poster"):
        raise ArrConnectionError("offline")

    entity.coordinator.client.async_get_cover = failing_cover
    result = asyncio.run(entity.async_image())
    assert result is not None
    assert b"<svg" in result
    assert entity._attr_content_type == "image/svg+xml"


def test_async_image_without_recent_items_uses_placeholder() -> None:
    """No recent items: straight to the placeholder, no cover request."""
    entity = _entity(_empty_snapshot())
    entity.coordinator.client.async_get_cover = MagicMock()
    result = asyncio.run(entity.async_image())
    entity.coordinator.client.async_get_cover.assert_not_called()
    assert entity._attr_content_type == "image/svg+xml"
    assert result is not None


def test_extra_state_attributes_scalars() -> None:
    """extra_state_attributes expose only scalar fields."""
    entity = _entity(_snapshot())
    attrs = entity.extra_state_attributes
    assert attrs == {"title": "The Test Show", "kind": KIND_SONARR, "item_id": 42}
