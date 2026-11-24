"""Frozen data models for Arr Studio. Pure data, no HA imports."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class MediaItem:
    entry_id: str
    kind: str
    id: int
    title: str
    subtitle: str = ""
    year: int | None = None
    added: str | None = None  # ISO-8601 Z
    poster: str | None = None  # /api/arr_studio/cover/... path
    fanart: str | None = None
    monitored: bool = True
    has_file: bool = False
    size: int = 0
    quality: str | None = None
    overview: str = ""
    meta: tuple[str, ...] = ()
    web_url: str | None = None

    def to_dict(self) -> dict:
        """Return JSON-safe primitives."""
        return {
            "entry_id": self.entry_id,
            "kind": self.kind,
            "id": self.id,
            "title": self.title,
            "subtitle": self.subtitle,
            "year": self.year,
            "added": self.added,
            "poster": self.poster,
            "fanart": self.fanart,
            "monitored": self.monitored,
            "has_file": self.has_file,
            "size": self.size,
            "quality": self.quality,
            "overview": self.overview,
            "meta": list(self.meta),
            "web_url": self.web_url,
        }


@dataclass(frozen=True, slots=True)
class QueueItem:
    entry_id: str
    kind: str
    id: int
    title: str
    subtitle: str = ""
    poster: str | None = None
    progress: float | None = None  # 0..1
    size: int = 0
    size_left: int = 0
    eta_seconds: int | None = None
    speed_bps: int | None = None
    status: str = "unknown"
    state: str = "unknown"
    protocol: str | None = None
    client: str | None = None
    quality: str | None = None
    error: str | None = None
    added: str | None = None
    web_url: str | None = None

    def to_dict(self) -> dict:
        """Return JSON-safe primitives."""
        return {
            "entry_id": self.entry_id,
            "kind": self.kind,
            "id": self.id,
            "title": self.title,
            "subtitle": self.subtitle,
            "poster": self.poster,
            "progress": self.progress,
            "size": self.size,
            "size_left": self.size_left,
            "eta_seconds": self.eta_seconds,
            "speed_bps": self.speed_bps,
            "status": self.status,
            "state": self.state,
            "protocol": self.protocol,
            "client": self.client,
            "quality": self.quality,
            "error": self.error,
            "added": self.added,
            "web_url": self.web_url,
        }


@dataclass(frozen=True, slots=True)
class ActivityItem:
    entry_id: str
    kind: str
    id: int
    event: str
    title: str
    subtitle: str = ""
    date: str | None = None
    poster: str | None = None
    quality: str | None = None
    web_url: str | None = None

    def to_dict(self) -> dict:
        """Return JSON-safe primitives."""
        return {
            "entry_id": self.entry_id,
            "kind": self.kind,
            "id": self.id,
            "event": self.event,
            "title": self.title,
            "subtitle": self.subtitle,
            "date": self.date,
            "poster": self.poster,
            "quality": self.quality,
            "web_url": self.web_url,
        }


@dataclass(frozen=True, slots=True)
class DiskInfo:
    path: str
    free: float = 0.0
    total: float = 0.0

    @property
    def used_pct(self) -> float | None:
        """Percentage of disk used, or None when total is unknown."""
        if self.total <= 0:
            return None
        return round((self.total - self.free) / self.total * 100, 1)

    def to_dict(self) -> dict:
        """Return JSON-safe primitives."""
        return {
            "path": self.path,
            "free": self.free,
            "total": self.total,
            "used_pct": self.used_pct,
        }


@dataclass(frozen=True, slots=True)
class ServerSnapshot:
    entry_id: str
    kind: str
    name: str
    version: str | None
    online: bool
    error: str | None
    library: tuple[MediaItem, ...]
    recent: tuple[MediaItem, ...]
    queue: tuple[QueueItem, ...]
    activity: tuple[ActivityItem, ...]
    disk: DiskInfo | None
    counts: dict[str, int]
    health: tuple[dict, ...] = ()
    speed_bps: int = 0
    updated_at: str | None = None

    def to_dict(self) -> dict:
        """Return JSON-safe primitives."""
        return {
            "entry_id": self.entry_id,
            "kind": self.kind,
            "name": self.name,
            "version": self.version,
            "online": self.online,
            "error": self.error,
            "library": [item.to_dict() for item in self.library],
            "recent": [item.to_dict() for item in self.recent],
            "queue": [item.to_dict() for item in self.queue],
            "activity": [item.to_dict() for item in self.activity],
            "disk": self.disk.to_dict() if self.disk is not None else None,
            "counts": dict(self.counts),
            "health": list(self.health),
            "speed_bps": self.speed_bps,
            "updated_at": self.updated_at,
        }
