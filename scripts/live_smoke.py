#!/usr/bin/env python3
"""Validate real Sonarr and Radarr servers using credentials from `.env`.

This script is a development aid only. It is not imported by the integration and
uses only the Python standard library.

It reads the following keys from the repository `.env` file:

    SONARR_URL, SONARR_API_KEY, RADARR_URL, RADARR_API_KEY

The URL must be the server root (no trailing slash, no ``/api`` or ``/api/v3``).

Usage:
    python3 scripts/live_smoke.py
    python3 scripts/live_smoke.py --only sonarr
    python3 scripts/live_smoke.py --insecure      # self-signed HTTPS certificates

The script never prints API keys.
"""

from __future__ import annotations

import argparse
import json
import re
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SERVERS = (
    ("SONARR", "sonarr", "Sonarr"),
    ("RADARR", "radarr", "Radarr"),
)

OK = "  ok   "
BAD = "  FAIL "


SECTION_ALIASES = {"sonarr": "SONARR", "radarr": "RADARR"}
SECTION_RE = re.compile(r"^\[?([A-Za-z][A-Za-z ]*?)\]?:$")
URL_KEYS = {"url", "host", "hostname", "base_url", "base url", "address"}
KEY_KEYS = {"api key", "api_key", "api-key", "apikey", "key", "token"}


def read_env(path: Path) -> dict[str, str]:
    """Parse a .env file.

    Accepts both the documented ``KEY=VALUE`` form and a plain notes form with
    sections:

        Radarr:
        url=http://192.168.1.10:7878
        API key=...

        Sonarr:
        url=http://192.168.1.10:8989
        API key=...
    """
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    section: str | None = None

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        header = SECTION_RE.match(line)
        if header:
            section = SECTION_ALIASES.get(header.group(1).strip().lower())
            continue

        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip().lower()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1].strip()
        if not value:
            continue

        if section and key in URL_KEYS:
            values[f"{section}_URL"] = value
        elif section and key in KEY_KEYS:
            values[f"{section}_API_KEY"] = value
        else:
            values[re.sub(r"[^A-Za-z0-9]+", "_", key).upper()] = value

    return values


def normalize_base_url(value: str) -> str:
    """Return a server root URL without trailing slash or API suffix."""
    url = value.strip().rstrip("/")
    if not url.startswith(("http://", "https://")):
        url = f"http://{url}"
    for suffix in ("/api/v3", "/api"):
        if url.endswith(suffix):
            url = url[: -len(suffix)]
    return url.rstrip("/")


def safe_url(value: str) -> str:
    """Return a display URL with credentials and query stripped."""
    parsed = urllib.parse.urlsplit(normalize_base_url(value))
    host = parsed.hostname or "unknown"
    port = f":{parsed.port}" if parsed.port else ""
    path = parsed.path.rstrip("/")
    return f"{parsed.scheme}://{host}{port}{path}"


class Client:
    """Tiny read-only Arr API client."""

    def __init__(self, base_url: str, api_key: str, insecure: bool = False) -> None:
        self.base_url = normalize_base_url(base_url)
        self.api_key = api_key.strip()
        self.context = ssl._create_unverified_context() if insecure else None

    def _open(self, path: str, params: dict[str, str] | None = None):
        url = f"{self.base_url}/api/v3{path}"
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"
        request = urllib.request.Request(
            url,
            headers={"X-Api-Key": self.api_key, "Accept": "application/json, image/*"},
        )
        return urllib.request.urlopen(request, timeout=20, context=self.context)

    def get_json(self, path: str, params: dict[str, str] | None = None):
        with self._open(path, params) as response:
            return json.loads(response.read().decode("utf-8"))

    def get_bytes(self, path: str) -> tuple[bytes, str, int]:
        with self._open(path) as response:
            return (
                response.read(),
                response.headers.get("Content-Type", "unknown"),
                response.status,
            )


def report(ok: bool, message: str) -> bool:
    print(f"{OK if ok else BAD}{message}")
    return ok


def describe_item(kind: str, item: dict) -> str:
    title = item.get("title") or item.get("sortTitle") or "Unknown"
    year = item.get("year")
    return f"{title} ({year})" if year else str(title)


def check_server(label: str, kind: str, base_url: str, api_key: str, insecure: bool) -> bool:
    """Run the validation checks for one server. Returns True when it is healthy."""
    print(f"\n{label} — {safe_url(base_url)}")
    client = Client(base_url, api_key, insecure)
    failures = 0

    try:
        status = client.get_json("/system/status")
    except urllib.error.HTTPError as err:
        hint = " (check the API key)" if err.code in (401, 403) else ""
        report(False, f"/system/status -> HTTP {err.code}{hint}")
        return False
    except (urllib.error.URLError, TimeoutError, OSError) as err:
        report(False, f"/system/status -> {err}")
        return False

    app_name = str(status.get("appName", "unknown"))
    version = str(status.get("version", "unknown"))
    instance = status.get("instanceName") or app_name
    if not report(True, f"/system/status: {app_name} {version} (instance: {instance})"):
        failures += 1
    if app_name.lower() != kind:
        report(False, f"appName is '{app_name}', expected '{kind}' — wrong server type?")
        failures += 1

    # Health
    try:
        health = client.get_json("/health")
        issues = len(health) if isinstance(health, list) else 0
        types = sorted({str(h.get("type")) for h in health if isinstance(h, dict)})
        report(True, f"/health: {issues} issue(s) {types if types else ''}".rstrip())
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as err:
        report(False, f"/health -> {err}")
        failures += 1

    # Disk space
    try:
        disks = client.get_json("/diskspace")
        if isinstance(disks, list) and disks:
            largest = max(disks, key=lambda d: float(d.get("totalSpace") or 0))
            free = float(largest.get("freeSpace") or 0) / 1e9
            total = float(largest.get("totalSpace") or 0) / 1e9
            report(True, f"/diskspace: {largest.get('path')} free {free:.1f} of {total:.1f} GB")
        else:
            report(False, "/diskspace returned no volumes")
            failures += 1
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as err:
        report(False, f"/diskspace -> {err}")
        failures += 1

    # Queue
    queue_params = {
        "page": "1",
        "pageSize": "100",
        "sortKey": "timeleft",
        "sortDirection": "ascending",
    }
    if kind == "sonarr":
        queue_params.update(includeSeries="true", includeEpisode="true")
    else:
        queue_params.update(includeMovie="true")
    try:
        queue = client.get_json("/queue", queue_params)
        records = queue.get("records") if isinstance(queue, dict) else None
        records = records or []
        total = queue.get("totalRecords", len(records)) if isinstance(queue, dict) else 0
        fields = set(records[0]) if records else set()
        expected = {"size", "sizeleft", "timeleft", "status", "protocol", "downloadClient"}
        missing = expected - fields if records else set()
        note = " fields ok" if records and not missing else ""
        if missing:
            note = f" missing fields: {sorted(missing)}"
        report(True, f"/queue: {total} record(s), sample keys{note}")
        if records:
            sample = records[0]
            progress = 0.0
            size = float(sample.get("size") or 0)
            if size > 0:
                progress = 100 * (1 - float(sample.get("sizeleft") or 0) / size)
            report(
                True,
                f"  sample: {sample.get('title', '?')[:60]} "
                f"({progress:.0f}%, {sample.get('status')}, {sample.get('protocol')})",
            )
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as err:
        report(False, f"/queue -> {err}")
        failures += 1

    # Library
    library_path = "/series" if kind == "sonarr" else "/movie"
    library: list[dict] = []
    try:
        raw = client.get_json(library_path)
        library = [item for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []
        report(True, f"{library_path}: {len(library)} item(s)")
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as err:
        report(False, f"{library_path} -> {err}")
        failures += 1

    recent = sorted(
        (item for item in library if item.get("added")),
        key=lambda item: str(item.get("added")),
        reverse=True,
    )[:3]
    for item in recent:
        images = item.get("images") or []
        cover_types = sorted(
            {
                str(image.get("coverType"))
                for image in images
                if isinstance(image, dict) and image.get("coverType")
            }
        )
        report(
            True,
            f"  recent: {describe_item(kind, item)} added {item.get('added')} covers {cover_types}",
        )

    # Poster via the API media-cover route (this is what the integration proxies)
    if recent:
        media_id = recent[0].get("id")
        try:
            body, content_type, status_code = client.get_bytes(
                f"/mediacover/{media_id}/poster.jpg"
            )
            report(
                bool(body),
                f"/mediacover/{media_id}/poster.jpg: HTTP {status_code}, "
                f"{content_type}, {len(body) / 1024:.1f} KB",
            )
            if not body:
                failures += 1
        except urllib.error.HTTPError as err:
            report(
                False,
                f"/mediacover/{media_id}/poster.jpg -> HTTP {err.code} "
                "(the arrival media cover may not be cached yet; remoteUrl fallback applies)",
            )
        except (urllib.error.URLError, TimeoutError, OSError) as err:
            report(False, f"/mediacover -> {err}")
            failures += 1

    # History
    history_params = {
        "page": "1",
        "pageSize": "20",
        "sortKey": "date",
        "sortDirection": "descending",
    }
    if kind == "sonarr":
        history_params.update(includeSeries="true", includeEpisode="true")
    else:
        history_params.update(includeMovie="true")
    try:
        history = client.get_json("/history", history_params)
        records = history.get("records") if isinstance(history, dict) else None
        records = records or []
        total = history.get("totalRecords", len(records)) if isinstance(history, dict) else 0
        events = sorted({str(record.get("eventType")) for record in records})
        report(True, f"/history: {total} record(s), event types {events}")
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as err:
        report(False, f"/history -> {err}")
        failures += 1

    # Calendar
    try:
        from datetime import date, timedelta

        today = date.today()
        params = {
            "start": today.isoformat(),
            "end": (today + timedelta(days=14)).isoformat(),
        }
        params["includeSeries" if kind == "sonarr" else "includeMovie"] = "true"
        calendar = client.get_json("/calendar", params)
        count = len(calendar) if isinstance(calendar, list) else 0
        report(True, f"/calendar: {count} item(s) in the next 14 days")
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError) as err:
        report(False, f"/calendar -> {err}")
        failures += 1

    return failures == 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", choices=["sonarr", "radarr"], help="validate one server only")
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="skip TLS certificate verification (self-signed certificates)",
    )
    parser.add_argument("--env", type=Path, default=ROOT / ".env", help="path to the .env file")
    args = parser.parse_args()

    env = read_env(args.env)
    if not env:
        print(f"FAIL no credentials found: {args.env} does not exist or is empty")
        print("      copy .env.example to .env and fill in your server URLs and API keys")
        return 1

    selected = [entry for entry in SERVERS if args.only is None or entry[1] == args.only]
    checked = 0
    failed = 0
    skipped = 0

    for prefix, kind, label in selected:
        base_url = env.get(f"{prefix}_URL", "").strip()
        api_key = env.get(f"{prefix}_API_KEY", "").strip()
        if not base_url or not api_key:
            print(f"\n{label} — skipped (set {prefix}_URL and {prefix}_API_KEY in .env)")
            skipped += 1
            continue
        checked += 1
        if not check_server(label, kind, base_url, api_key, args.insecure):
            failed += 1

    print()
    if failed:
        print(f"RESULT: {failed} of {checked} server(s) failed, {skipped} skipped")
        return 1
    if not checked:
        print("RESULT: nothing checked — no complete credentials in .env")
        return 1
    print(f"RESULT: {checked} server(s) OK, {skipped} skipped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
