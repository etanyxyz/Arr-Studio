"""Pure normalisation functions used by Arr Studio. No HA imports, no I/O."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from custom_components.arr_studio.models import ActivityItem, DiskInfo, MediaItem, QueueItem

META_LIMIT = 3
OVERVIEW_LIMIT = 600

# History events surfaced by the panel (plan §4.2). `grabbed` gets a friendly
# label; the rest pass through unchanged. Unknown/irrelevant events make
# normalize_history return None (plan §12.1).
RELEVANT_EVENTS = {
    "grabbed": "Grabbed",
    "downloadFolderImported": "downloadFolderImported",
    "downloadFailed": "downloadFailed",
    "episodeFileDeleted": "episodeFileDeleted",
    "episodeFileRenamed": "episodeFileRenamed",
    "movieFileDeleted": "movieFileDeleted",
    "movieFileRenamed": "movieFileRenamed",
}


def cover_path(entry_id: str, kind: str, media_id: int, variant: str) -> str:
    """Build a HA media-cover path for a given entry."""
    return f"/api/arr_studio/cover/{entry_id}/{kind}/{media_id}/{variant}"


def _text(value: Any) -> str:
    """Trim a value to a string (empty when not a string)."""
    return value.strip() if isinstance(value, str) else ""


def _quality_name(raw: dict) -> str | None:
    """Quality name from `quality.quality.name`, falling back to `quality.name`."""
    quality = raw.get("quality")
    if not isinstance(quality, dict):
        return None
    inner = quality.get("quality")
    if isinstance(inner, dict):
        return _text(inner.get("name")) or None
    return _text(quality.get("name")) or None


def _media_meta(studio_or_network: str | None, genres: list[str]) -> tuple[str, ...]:
    """network/studio first, then genres; capped at 3 total (plan §8.6)."""
    meta: list[str] = []
    if studio_or_network:
        meta.append(studio_or_network)
    for genre in genres:
        if genre:
            meta.append(genre)
    return tuple(meta[:META_LIMIT])


def _field(item: Any, name: str) -> Any:
    """Read `name` from a dict or dataclass item."""
    return item.get(name) if isinstance(item, dict) else getattr(item, name, None)


def pick_image(images: list | None, cover_type: str) -> str | None:
    """Return the URL of the first image of `cover_type`, else None.

    Prefers `remoteUrl` (plan §8.6), falling back to `url` (fixtures/tests).
    """
    if not images:
        return None
    for item in images:
        if not isinstance(item, dict) or item.get("coverType") != cover_type:
            continue
        url = item.get("remoteUrl") or item.get("url")
        if url:
            return url
    return None


def iso_utc(value: str | None) -> str | None:
    """Return an ISO-8601 UTC string normalised to a trailing `Z`, or None."""
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return str(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def compute_progress(size: int, size_left: int) -> float | None:
    """Fraction of `size` already downloaded, clamped to 0..1; None when size <= 0."""
    if size <= 0:
        return None
    progress = (size - size_left) / size
    return round(max(0.0, min(1.0, progress)), 6)


def parse_timeleft(value: str | None) -> int | None:
    """Parse a .NET TimeSpan (`d.HH:MM:SS` / `HH:MM:SS`) or bare seconds to seconds."""
    if not value:
        return None
    text = str(value).strip()
    days = 0
    if "." in text:
        day_part, text = text.split(".", 1)
        if not day_part.isdigit():
            return None
        days = int(day_part)
    parts = text.split(":")
    if len(parts) == 3 and all(part.isdigit() for part in parts):
        hours, minutes, seconds = (int(part) for part in parts)
        return days * 86400 + hours * 3600 + minutes * 60 + seconds
    if len(parts) == 1 and parts[0].isdigit():
        return days * 86400 + int(parts[0])
    return None


def parse_datetime(value: str | None) -> datetime | None:
    """Parse an ISO-8601 UTC timestamp, stripping the trailing `Z`."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


def normalize_series(entry_id: str, raw: dict, base_url: str) -> MediaItem:
    """Normalise a Sonarr library series entry into a MediaItem."""
    media_id = raw.get("id")
    title = raw.get("title") or raw.get("sortTitle") or "Unknown"
    year = raw.get("year")
    network = raw.get("network")
    images = raw.get("images")

    if network:
        subtitle = f"{network} · {year}" if year else str(network)
    elif year:
        subtitle = str(year)
    else:
        subtitle = ""

    return MediaItem(
        entry_id=entry_id,
        kind="sonarr",
        id=media_id,
        title=_text(title),
        subtitle=_text(subtitle),
        year=year,
        added=iso_utc(raw.get("added")),
        poster=cover_path(entry_id, "sonarr", media_id, "poster") if pick_image(images, "poster") else None,
        fanart=cover_path(entry_id, "sonarr", media_id, "fanart") if pick_image(images, "fanart") else None,
        monitored=bool(raw.get("monitored", True)),
        has_file=bool(raw.get("hasFile", False)),
        size=raw.get("sizeOnDisk", 0) or 0,
        quality=_quality_name(raw),
        overview=_text(raw.get("overview"))[:OVERVIEW_LIMIT],
        meta=_media_meta(network, raw.get("genres") or []),
        web_url=raw.get("webUrl"),
    )


def normalize_movie(entry_id: str, raw: dict, base_url: str) -> MediaItem:
    """Normalise a Radarr movie entry into a MediaItem."""
    media_id = raw.get("id")
    title = raw.get("title") or raw.get("sortTitle") or "Unknown"
    year = raw.get("year")
    studio = raw.get("studio")
    images = raw.get("images")
    movie_file = raw.get("movieFile")

    if studio:
        subtitle = f"{studio} · {year}" if year else str(studio)
    elif year:
        subtitle = str(year)
    else:
        subtitle = ""

    return MediaItem(
        entry_id=entry_id,
        kind="radarr",
        id=media_id,
        title=_text(title),
        subtitle=_text(subtitle),
        year=year,
        added=iso_utc(raw.get("added")),
        poster=cover_path(entry_id, "radarr", media_id, "poster") if pick_image(images, "poster") else None,
        fanart=cover_path(entry_id, "radarr", media_id, "fanart") if pick_image(images, "fanart") else None,
        monitored=bool(raw.get("monitored", True)),
        has_file=bool(raw.get("hasFile", False)),
        size=raw.get("sizeOnDisk", 0) or 0,
        quality=_quality_name(movie_file) if isinstance(movie_file, dict) else None,
        overview=_text(raw.get("overview"))[:OVERVIEW_LIMIT],
        meta=_media_meta(studio, raw.get("genres") or []),
        web_url=raw.get("webUrl"),
    )


def normalize_queue(entry_id: str, kind: str, raw: dict, base_url: str) -> QueueItem:
    """Normalise a queue record into a QueueItem."""
    episode = raw.get("episode") if isinstance(raw.get("episode"), dict) else {}
    movie = raw.get("movie") if isinstance(raw.get("movie"), dict) else {}
    series = raw.get("series") if isinstance(raw.get("series"), dict) else {}
    nested = series or movie

    title = raw.get("title") or nested.get("title") or raw.get("sortTitle") or "Unknown"
    if kind == "sonarr":
        season = raw.get("seasonNumber", episode.get("seasonNumber"))
        number = raw.get("episodeNumber", episode.get("episodeNumber"))
        episode_title = raw.get("episodeTitle") or episode.get("title")
        if season is not None and number is not None and episode_title:
            subtitle = f"S{season:02d}E{number:02d} · {episode_title}"
        else:
            subtitle = title
    else:
        year = raw.get("year", movie.get("year"))
        studio = raw.get("studio") or movie.get("studio")
        if studio and year:
            subtitle = f"{studio} · {year}"
        elif year:
            subtitle = str(year)
        else:
            subtitle = title

    media_id = raw.get("id")
    size = raw.get("size", 0) or 0
    size_left = raw.get("sizeleft", 0) or 0
    return QueueItem(
        entry_id=entry_id,
        kind=kind,
        id=media_id,
        title=_text(title),
        subtitle=_text(subtitle),
        # Queue items may carry no inline images; the cover view resolves the
        # HA path and falls back to a placeholder on 404 (plan §8.6).
        poster=cover_path(entry_id, kind, media_id, "poster"),
        progress=compute_progress(size, size_left),
        size=size,
        size_left=size_left,
        eta_seconds=parse_timeleft(raw.get("timeleft")),
        speed_bps=raw.get("speedbps"),
        status=_text(raw.get("status")) or "unknown",
        state=_text(raw.get("trackedDownloadState")) or "unknown",
        protocol=raw.get("protocol"),
        client=raw.get("downloadClient"),
        quality=_quality_name(raw),
        error=raw.get("errorMessage"),
        added=iso_utc(raw.get("added")),
        web_url=raw.get("webUrl"),
    )


def normalize_history(entry_id: str, kind: str, raw: dict, base_url: str) -> ActivityItem | None:
    """Normalise a history record into an ActivityItem, or None if irrelevant.

    Unknown/irrelevant events return None (plan §12.1).
    """
    if not raw:
        return None
    event = RELEVANT_EVENTS.get(raw.get("eventType", ""))
    if event is None:
        return None

    episode = raw.get("episode") if isinstance(raw.get("episode"), dict) else {}
    movie = raw.get("movie") if isinstance(raw.get("movie"), dict) else {}
    title = raw.get("title") or raw.get("sourceTitle") or "Unknown"
    source_title = raw.get("sourceTitle") or title

    if kind == "sonarr":
        season = episode.get("seasonNumber")
        number = episode.get("episodeNumber")
        episode_title = episode.get("title")
        if season is not None and number is not None and episode_title:
            subtitle = f"S{season:02d}E{number:02d} · {episode_title}"
        else:
            subtitle = source_title
    else:
        year = movie.get("year")
        subtitle = str(year) if year else source_title

    return ActivityItem(
        entry_id=entry_id,
        kind=kind,
        id=raw.get("id"),
        event=event,
        title=_text(title),
        subtitle=_text(subtitle),
        date=iso_utc(raw.get("date")),
        poster=raw.get("poster"),
        quality=_quality_name(raw),
        web_url=raw.get("webUrl"),
    )


def normalize_health(raw: list | None) -> tuple[dict, ...]:
    """Keep only source/type/message per health entry (plan §8.6)."""
    if not raw:
        return ()
    return tuple(
        {
            "source": _text(item.get("source")),
            "type": _text(item.get("type")),
            "message": _text(item.get("message")),
        }
        for item in raw
        if isinstance(item, dict)
    )


def normalize_disks(raw: list | None) -> tuple[DiskInfo, ...]:
    """Normalise a diskspace list into a tuple of DiskInfo objects."""
    if not raw:
        return ()
    return tuple(
        DiskInfo(path=d.get("path"), free=d.get("freeSpace", 0) or 0, total=d.get("totalSpace", 0) or 0)
        for d in raw
        if isinstance(d, dict)
    )


def compute_missing(kind: str, library: list[dict], show_unmonitored: bool) -> int:
    """Count missing library items (plan §12.1).

    Unmonitored items only count when `show_unmonitored` is True; monitored
    items count when they explicitly have no file.
    """
    count = 0
    for item in library:
        if not isinstance(item, dict):
            continue
        if not item.get("monitored", True):
            if show_unmonitored:
                count += 1
        elif item.get("hasFile") is False:
            count += 1
    return count


def merge_counts(**kwargs: int) -> dict[str, int]:
    """Merge counts from multiple sources into a single dict."""
    result: dict[str, int] = {}
    for key, value in kwargs.items():
        result[key] = result.get(key, 0) + value
    return result


def web_url(kind: str, base_url: str, title_slug: str | None) -> str | None:
    """Build a web URL for a library entry."""
    if not title_slug:
        return None
    return f"{base_url}/{kind}/{title_slug}"


def sort_newest_first(items: tuple[Any, ...] | list[Any]) -> tuple[Any, ...]:
    """Sort by `added` descending with None last; stable tiebreak by title."""
    seq = list(items)
    seq.sort(key=lambda item: _text(_field(item, "title")))
    seq.sort(
        key=lambda item: (0, "") if _field(item, "added") is None else (1, _text(_field(item, "added"))),
        reverse=True,
    )
    return tuple(seq)
