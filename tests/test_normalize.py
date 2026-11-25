"""Test the Arr normalisation functions."""

from custom_components.arr_studio.normalize import (
    compute_missing,
    compute_progress,
    cover_path,
    iso_utc,
    merge_counts,
    normalize_disks,
    normalize_health,
    normalize_history,
    normalize_movie,
    normalize_queue,
    normalize_series,
    parse_datetime,
    parse_timeleft,
    pick_image,
    sort_newest_first,
    web_url,
)


class TestCoverPath:
    def test_basic(self):
        assert cover_path("abc", "sonarr", 42, "poster") == "/api/arr_studio/cover/abc/sonarr/42/poster"

    def test_variant(self):
        assert cover_path("abc", "radarr", 1, "fanart") == "/api/arr_studio/cover/abc/radarr/1/fanart"


class TestPickImage:
    def test_find_poster(self):
        images = [
            {"coverType": "fanart", "url": "fanart_url"},
            {"coverType": "poster", "url": "poster_url"},
        ]
        assert pick_image(images, "poster") == "poster_url"

    def test_find_fanart(self):
        images = [
            {"coverType": "fanart", "url": "fanart_url"},
        ]
        assert pick_image(images, "fanart") == "fanart_url"

    def test_no_match(self):
        images = [{"coverType": "banner", "url": "banner_url"}]
        assert pick_image(images, "poster") is None

    def test_empty_list(self):
        assert pick_image([], "poster") is None

    def test_none_list(self):
        assert pick_image(None, "poster") is None


class TestIsoUtc:
    def test_returns_string(self):
        assert iso_utc("2026-11-23T16:00:00Z") == "2026-11-23T16:00:00Z"

    def test_none_returns_none(self):
        assert iso_utc(None) is None

    def test_empty_returns_none(self):
        assert iso_utc("") is None


class TestComputeProgress:
    def test_exact(self):
        assert compute_progress(1000, 500) == 0.5

    def test_zero_size(self):
        assert compute_progress(0, 100) is None

    def test_negative_size(self):
        assert compute_progress(-100, 50) is None


class TestParseTimeleft:
    def test_hh_mm_ss(self):
        assert parse_timeleft("00:05:12") == 312

    def test_days(self):
        assert parse_timeleft("1.02:03:04") == 93784

    def test_just_seconds(self):
        assert parse_timeleft("120") == 120

    def test_empty(self):
        assert parse_timeleft("") is None

    def test_none(self):
        assert parse_timeleft(None) is None


class TestParseDatetime:
    def test_valid(self):
        result = parse_datetime("2026-11-23T16:00:00Z")
        assert result is not None
        assert result.year == 2026

    def test_none(self):
        assert parse_datetime(None) is None

    def test_empty(self):
        assert parse_datetime("") is None


class TestNormalizeSeries:
    def test_basic(self):
        raw = {
            "id": 34,
            "title": "Severance",
            "sortTitle": "Severance",
            "year": 2022,
            "network": "Apple TV+",
            "genres": ["Sci-Fi", "Drama"],
            "added": "2026-11-23T15:40:00Z",
            "monitored": True,
            "hasFile": True,
            "sizeOnDisk": 4823449600,
            "overview": "Mark leads a team...",
        }
        result = normalize_series("entry1", raw, "http://test.local")
        assert result.kind == "sonarr"
        assert result.id == 34
        assert result.title == "Severance"
        assert result.subtitle == "Apple TV+ · 2022"
        assert result.year == 2022
        assert result.monitored is True
        assert result.has_file is True
        assert result.size == 4823449600
        assert result.overview == "Mark leads a team..."
        assert result.meta == ("Apple TV+", "Sci-Fi", "Drama")

    def test_no_network(self):
        raw = {"id": 1, "title": "Film", "year": 2020, "genres": []}
        result = normalize_series("e1", raw, "http://test.local")
        assert result.subtitle == "2020"
        assert result.meta == ()


class TestNormalizeMovie:
    def test_basic(self):
        raw = {
            "id": 1,
            "title": "The Last Frontier",
            "sortTitle": "The Last Frontier",
            "year": 2024,
            "studio": "Dark Picture",
            "genres": ["Action", "Sci-Fi"],
            "added": "2026-11-20T10:00:00Z",
            "monitored": True,
            "hasFile": True,
            "sizeOnDisk": 1234567890,
            "overview": "A team...",
        }
        result = normalize_movie("entry1", raw, "http://test.local")
        assert result.kind == "radarr"
        assert result.id == 1
        assert result.title == "The Last Frontier"
        assert result.subtitle == "Dark Picture · 2024"
        assert result.year == 2024
        assert result.overview == "A team..."


class TestNormalizeQueue:
    def test_sonarr_queue_entry(self):
        raw = {
            "id": 1201,
            "seriesId": 34,
            "episodeId": 9001,
            "seasonNumber": 2,
            "title": "Severance.S02E04.1080p.WEB-DL",
            "status": "downloading",
            "trackedDownloadState": "downloading",
            "trackedDownloadStatus": "ok",
            "size": 1825361100,
            "sizeleft": 1056964608,
            "timeleft": "00:05:12",
            "estimatedCompletionTime": "2026-11-23T16:05:12Z",
            "added": "2026-11-23T15:40:00Z",
            "protocol": "torrent",
            "downloadClient": "qBittorrent",
            "indexer": "TorrentLeech",
            "quality": {"quality": {"id": 3, "name": "WEBDL-1080p"}},
            "errorMessage": None,
            "series": {"id": 34, "title": "Severance", "titleSlug": "severance", "year": 2022},
            "episode": {"seasonNumber": 2, "episodeNumber": 4, "title": "Woe's Hollow"},
        }
        result = normalize_queue("entry1", "sonarr", raw, "http://test.local")
        assert result.kind == "sonarr"
        assert result.id == 1201
        assert result.title == "Severance.S02E04.1080p.WEB-DL"
        assert result.subtitle == "S02E04 · Woe's Hollow"
        assert result.status == "downloading"
        assert result.protocol == "torrent"
        # Cover path keys off the series id, not the queue id (plan §8.14).
        assert result.poster == "/api/arr_studio/cover/entry1/sonarr/34/poster"

    def test_radarr_queue_entry(self):
        raw = {
            "id": 101,
            "movieId": 1,
            "movie": {"id": 1, "title": "The Last Frontier", "year": 2024},
            "size": 1825361100,
            "sizeleft": 1056964608,
            "timeleft": "00:05:12",
            "status": "downloading",
            "protocol": "torrent",
            "downloadClient": "qBittorrent",
            "quality": {"quality": {"name": "WEBDL-1080p"}},
        }
        result = normalize_queue("entry1", "radarr", raw, "http://test.local")
        assert result.kind == "radarr"
        assert result.id == 101
        assert result.title == "The Last Frontier"
        assert result.subtitle == "2024"
        # Cover path keys off the movie id, not the queue id (plan §8.14).
        assert result.poster == "/api/arr_studio/cover/entry1/radarr/1/poster"

    def test_queue_cover_falls_back_to_series_id_field(self):
        raw = {
            "id": 500,
            "seriesId": 7,
            "title": "Show.S01E01.1080p.WEB-DL",
            "status": "downloading",
        }
        result = normalize_queue("entry1", "sonarr", raw, "http://test.local")
        assert result.id == 500
        assert result.poster == "/api/arr_studio/cover/entry1/sonarr/7/poster"


class TestNormalizeHistory:
    def test_download_folder_imported(self):
        raw = {
            "id": 1,
            "date": "2026-11-23T15:12:00Z",
            "eventType": "downloadFolderImported",
            "sourceTitle": "The Last Frontier",
            "quality": {"quality": {"name": "WEBDL-1080p"}},
            "data": {},
        }
        result = normalize_history("entry1", "radarr", raw, "http://test.local")
        assert result.event == "downloadFolderImported"
        assert result.title == "The Last Frontier"
        assert result.quality == "WEBDL-1080p"

    def test_grabbed(self):
        raw = {
            "id": 2,
            "date": "2026-11-23T14:30:00Z",
            "eventType": "grabbed",
            "sourceTitle": "Film",
        }
        result = normalize_history("entry1", "sonarr", raw, "http://test.local")
        assert result.event == "Grabbed"

    def test_unknown_event_type(self):
        raw = {
            "id": 3,
            "date": "2026-11-23T14:30:00Z",
            "eventType": "some_unknown_event",
        }
        result = normalize_history("entry1", "sonarr", raw, "http://test.local")
        assert result is None


class TestNormalizeHealth:
    def test_normal(self):
        raw = [
            {"source": "IndexerLongTermStatusCheck", "type": "warning", "message": "slow", "wikiUrl": "http://..."},
        ]
        result = normalize_health(raw)
        assert isinstance(result, tuple)
        assert len(result) == 1

    def test_empty(self):
        assert normalize_health(None) == ()


class TestNormalizeDisks:
    def test_normal(self):
        raw = [{"path": "/tv", "freeSpace": 872000000000, "totalSpace": 4000000000000}]
        result = normalize_disks(raw)
        assert len(result) == 1
        assert result[0].path == "/tv"
        assert result[0].free == 872000000000
        assert result[0].total == 4000000000000

    def test_empty(self):
        assert normalize_disks(None) == ()


class TestComputeMissing:
    def test_all_monitored(self):
        library = [
            {"id": 1, "monitored": True},
            {"id": 2, "monitored": True},
        ]
        assert compute_missing("sonarr", library, False) == 0

    def test_with_unmonitored(self):
        library = [
            {"id": 1, "monitored": True},
            {"id": 2, "monitored": False},
        ]
        assert compute_missing("sonarr", library, False) == 0

    def test_show_unmonitored_false(self):
        library = [
            {"id": 1, "monitored": False},
        ]
        assert compute_missing("sonarr", library, False) == 0

    def test_show_unmonitored_true(self):
        library = [
            {"id": 1, "monitored": False},
        ]
        assert compute_missing("sonarr", library, True) == 1


class TestMergeCounts:
    def test_merge(self):
        result = merge_counts(library=10, queue=5, downloading=3)
        assert result == {"library": 10, "queue": 5, "downloading": 3}


class TestWebUrl:
    def test_basic(self):
        assert web_url("sonarr", "http://test.local", "severance") == "http://test.local/sonarr/severance"

    def test_no_slug(self):
        assert web_url("sonarr", "http://test.local", "") is None


class TestSortNewestFirst:
    def test_sort_descending(self):
        items = [
            {"added": "2026-11-23T15:00:00Z", "title": "A"},
            {"added": "2026-11-23T14:00:00Z", "title": "B"},
            {"added": "2026-11-23T15:30:00Z", "title": "C"},
        ]
        result = sort_newest_first(items)
        assert result[0]["added"] >= result[1]["added"]
        assert result[0]["title"] == "C"

    def test_none_last(self):
        items = [
            {"added": "2026-11-23T15:00:00Z", "title": "A"},
            {"added": None, "title": "B"},
        ]
        result = sort_newest_first(items)
        assert result[1]["added"] is None
