#!/usr/bin/env python3
"""Repository preflight checks for the Arr Studio integration.

Usage:
    python3 scripts/preflight.py --phase 0
    python3 scripts/preflight.py --phase 6

The phase argument is cumulative: phase 6 also checks everything required by
phases 0 to 5. Each check prints PASS or FAIL; the script exits 1 if any check
failed.
"""

from __future__ import annotations

import argparse
import compileall
import json
import re
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PKG = ROOT / "custom_components" / "arr_studio"
FRONTEND = PKG / "frontend"
FIXTURES = ROOT / "tests" / "fixtures"

DOMAIN = "arr_studio"
VERSION_RE = re.compile(r'^VERSION\s*=\s*"([^"]+)"', re.MULTILINE)

SENSOR_KEYS = ("queue", "downloading", "recent", "library", "missing", "disk_free", "health")

FRONTEND_FILES = (
    "panel.js",
    "api.js",
    "dom.js",
    "format.js",
    "icons.js",
    "styles.js",
    "state.js",
    "render-hero.js",
    "render-recent.js",
    "render-queue.js",
    "render-activity.js",
    "placeholder.svg",
)

REQUIRED_PHASE_FILES: dict[int, tuple[str, ...]] = {
    0: (
        ".gitignore",
        ".env.example",
        "LICENSE",
        "hacs.json",
        "pyproject.toml",
        "README.md",
        "docs/PLAN.md",
        "scripts/preflight.py",
        "scripts/check_frontend.mjs",
        "scripts/live_smoke.py",
    ),
    1: (
        "custom_components/arr_studio/const.py",
        "custom_components/arr_studio/api.py",
        "custom_components/arr_studio/models.py",
        "custom_components/arr_studio/normalize.py",
        "tests/conftest.py",
        "tests/test_api.py",
        "tests/test_normalize.py",
        "tests/fixtures/sonarr_status.json",
        "tests/fixtures/sonarr_queue.json",
        "tests/fixtures/sonarr_history.json",
        "tests/fixtures/sonarr_series.json",
        "tests/fixtures/sonarr_diskspace.json",
        "tests/fixtures/radarr_movie.json",
        "tests/fixtures/radarr_queue.json",
        "tests/fixtures/radarr_history.json",
    ),
    2: (
        "custom_components/arr_studio/manifest.json",
        "custom_components/arr_studio/strings.json",
        "custom_components/arr_studio/translations/en.json",
        "custom_components/arr_studio/coordinator.py",
        "custom_components/arr_studio/config_flow.py",
        "custom_components/arr_studio/entity.py",
        "custom_components/arr_studio/__init__.py",
        "custom_components/arr_studio/diagnostics.py",
        "custom_components/arr_studio/services.py",
    ),
    3: (
        "custom_components/arr_studio/sensor.py",
        "custom_components/arr_studio/binary_sensor.py",
        "custom_components/arr_studio/image.py",
        "custom_components/arr_studio/button.py",
    ),
    4: (
        "custom_components/arr_studio/payload.py",
        "custom_components/arr_studio/http_views.py",
        "tests/test_payload.py",
    ),
    5: (
        "custom_components/arr_studio/frontend.py",
        "custom_components/arr_studio/brand/icon.png",
        "custom_components/arr_studio/brand/logo.png",
        *tuple(f"custom_components/arr_studio/frontend/{name}" for name in FRONTEND_FILES),
    ),
    6: (
        ".github/workflows/validate.yml",
        "docs/ARCHITECTURE.md",
        "docs/UI.md",
        "docs/TESTING.md",
        "examples/automation-download-complete.yaml",
        "info.md",
        "README.md",
    ),
    7: (
        "docs/images/panel-overview.png",
        "docs/images/panel-downloads.png",
        "docs/images/panel-detail.png",
        "docs/images/entities.png",
    ),
}

MANIFEST_REQUIRED = (
    "domain",
    "name",
    "codeowners",
    "config_flow",
    "documentation",
    "integration_type",
    "iot_class",
    "issue_tracker",
    "requirements",
    "version",
)

FORBIDDEN_PY = (
    (re.compile(r"\bimport\s+requests\b"), "use aiohttp instead of requests"),
    (re.compile(r"\b(?:eval|exec)\s*\("), "eval/exec is forbidden"),
    (re.compile(r"verify_ssl\s*=\s*False"), "do not hardcode verify_ssl=False"),
    (re.compile(r"\.innerHTML\b"), "innerHTML belongs to no Python file"),
)

FORBIDDEN_JS = (
    (re.compile(r"\.innerHTML\b"), "innerHTML is forbidden; use el()"),
    (re.compile(r"\.outerHTML\b"), "outerHTML is forbidden; use el()"),
    (re.compile(r"insertAdjacentHTML"), "insertAdjacentHTML is forbidden"),
    (re.compile(r"\beval\s*\("), "eval is forbidden"),
    (re.compile(r"new\s+Function\s*\("), "new Function is forbidden"),
    (re.compile(r"document\.write"), "document.write is forbidden"),
    (re.compile(r"\bapi_?key\b", re.IGNORECASE), "API key reference in frontend code"),
    (re.compile(r"X-Api-Key", re.IGNORECASE), "API key header in frontend code"),
    (re.compile(r"\bhttps?://"), "absolute URL in frontend code"),
)

results: list[tuple[str, bool, str]] = []


def record(name: str, ok: bool, detail: str = "") -> bool:
    results.append((name, ok, detail))
    return ok


def read_json(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as err:
        record(f"json:{path.relative_to(ROOT)}", False, str(err))
        return None
    if not isinstance(data, dict):
        record(f"json:{path.relative_to(ROOT)}", False, "top level must be an object")
        return None
    return data


def strip_js_comments(source: str) -> str:
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
    lines = []
    for line in source.splitlines():
        if "preflight: allow" in line:
            lines.append("")
            continue
        lines.append(re.sub(r"(?<!:)//.*$", "", line))
    return "\n".join(lines)


def check_required_files(phase: int) -> None:
    missing: list[str] = []
    for required_phase in sorted(REQUIRED_PHASE_FILES):
        if required_phase > phase:
            break
        for relative in REQUIRED_PHASE_FILES[required_phase]:
            if not (ROOT / relative).is_file():
                missing.append(relative)
    record("required files", not missing, ", ".join(missing[:10]))


def check_env_safety() -> None:
    gitignore = ROOT / ".gitignore"
    if not gitignore.is_file():
        record(".env ignored", False, ".gitignore missing")
        return
    lines = {line.strip() for line in gitignore.read_text(encoding="utf-8").splitlines()}
    if ".env" not in lines:
        record(".env ignored", False, ".gitignore does not list .env")
        return
    record(".env ignored", True)

    if not (ROOT / ".env").exists():
        return
    try:
        ignored = subprocess.run(
            ["git", "check-ignore", "-q", ".env"], cwd=ROOT, check=False
        )
    except OSError:
        return
    record(".env consults gitignore", ignored.returncode == 0, "git check-ignore failed")
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", ".env"],
        cwd=ROOT,
        check=False,
        capture_output=True,
    )
    record(".env not tracked", tracked.returncode != 0, "the .env file is tracked by git")

    history = subprocess.run(
        ["git", "log", "--all", "--format=%H", "--", ".env"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    record(
        ".env never committed",
        not history.stdout.strip(),
        "the .env file appears in git history",
    )


def check_hacs() -> None:
    data = read_json(ROOT / "hacs.json")
    if data is None:
        return
    problems = [key for key in ("name", "homeassistant") if key not in data]
    if data.get("name") != "Arr Studio":
        problems.append("name must be 'Arr Studio'")
    if data.get("content_in_root"):
        problems.append("content_in_root must not be set")
    record("hacs.json", not problems, ", ".join(problems))


def check_const() -> str | None:
    path = PKG / "const.py"
    if not path.is_file():
        return None
    match = VERSION_RE.search(path.read_text(encoding="utf-8"))
    if not match:
        record("const.py VERSION", False, "VERSION assignment not found")
        return None
    record("const.py VERSION", True)
    return match.group(1)


def check_manifest(version: str | None) -> None:
    path = PKG / "manifest.json"
    data = read_json(path)
    if data is None:
        return
    problems = [key for key in MANIFEST_REQUIRED if key not in data]
    if data.get("domain") != DOMAIN:
        problems.append(f"domain must be '{DOMAIN}'")
    if data.get("requirements") != []:
        problems.append("requirements must be []")
    dependencies = data.get("dependencies") or []
    for dependency in ("http", "frontend"):
        if dependency not in dependencies:
            problems.append(f"dependencies must include '{dependency}'")
    if version and data.get("version") != version:
        problems.append(f"version {data.get('version')!r} != const.VERSION {version!r}")
    record("manifest.json", not problems, ", ".join(problems))


def check_translations() -> None:
    strings = read_json(PKG / "strings.json")
    english = read_json(PKG / "translations" / "en.json")
    if strings is None or english is None:
        return
    record("translations match", strings == english, "strings.json != translations/en.json")


def check_png(path: Path, expected: tuple[int, int]) -> None:
    try:
        data = path.read_bytes()
    except OSError as err:
        record(f"png:{path.name}", False, str(err))
        return
    if data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        record(f"png:{path.name}", False, "not a PNG file")
        return
    width, height = struct.unpack(">II", data[16:24])
    record(f"png:{path.name}", (width, height) == expected, f"{width}x{height}, expected {expected[0]}x{expected[1]}")


def check_sensor_keys() -> None:
    path = PKG / "sensor.py"
    if not path.is_file():
        return
    source = path.read_text(encoding="utf-8")
    missing = [key for key in SENSOR_KEYS if not re.search(rf"[\"']{key}[\"']", source)]
    record("sensor keys", not missing, f"missing keys: {missing}")


def check_payload_keys() -> None:
    path = PKG / "payload.py"
    if not path.is_file():
        return
    source = path.read_text(encoding="utf-8")
    required = ("servers", "recent", "queue", "activity", "errors")
    missing = [key for key in required if f'"{key}"' not in source and f"'{key}'" not in source]
    leaked = [token for token in ("api_key", "API_KEY", "apikey") if token in source]
    record("payload contract", not missing, f"missing keys: {missing}")
    record("payload has no api key", not leaked, f"found: {leaked}")


def check_frontend_security(phase: int) -> None:
    if phase < 5 or not FRONTEND.is_dir():
        return
    problems: list[str] = []
    files = sorted(FRONTEND.rglob("*.js"))
    for path in files:
        source = strip_js_comments(path.read_text(encoding="utf-8"))
        for pattern, message in FORBIDDEN_JS:
            if pattern.search(source):
                problems.append(f"{path.relative_to(ROOT)}: {message}")
        if re.search(r"\b(api_key|API_KEY|apikey)\b", source):
            problems.append(f"{path.relative_to(ROOT)}: API key reference")
    record("frontend forbidden patterns", not problems, "; ".join(problems[:6]))

    panel = FRONTEND / "panel.js"
    if panel.is_file():
        source = panel.read_text(encoding="utf-8")
        record(
            "panel element registered",
            'customElements.define("arr-studio-panel"' in source,
            "panel.js must define arr-studio-panel",
        )

    frontend_py = PKG / "frontend.py"
    if frontend_py.is_file():
        source = frontend_py.read_text(encoding="utf-8")
        problems = [
            token
            for token in ("_panel_custom", "async_register_static_paths", "FRONTEND_STATIC_URL")
            if token not in source
        ]
        record("frontend registration", not problems, f"missing: {problems}")


def check_workflow() -> None:
    path = ROOT / ".github" / "workflows" / "validate.yml"
    if not path.is_file():
        return
    source = path.read_text(encoding="utf-8")
    problems = [
        token
        for token in ("hassfest", "hacs/action", "pytest", "check_frontend.mjs")
        if token not in source
    ]
    record("ci workflow", not problems, f"missing: {problems}")


def check_python(phase: int) -> None:
    if phase < 1:
        return
    targets = [ROOT / "custom_components", ROOT / "scripts", ROOT / "tests"]
    ok = True
    for target in targets:
        if not target.is_dir():
            continue
        ok = compileall.compile_dir(str(target), quiet=2, force=True) and ok
    record("python compiles", ok, "compileall reported errors")

    problems: list[str] = []
    for path in sorted((ROOT / "custom_components").rglob("*.py")):
        source = path.read_text(encoding="utf-8")
        for pattern, message in FORBIDDEN_PY:
            if pattern.search(source):
                problems.append(f"{path.relative_to(ROOT)}: {message}")
    record("python forbidden patterns", not problems, "; ".join(problems[:6]))


def main() -> int:
    parser = argparse.ArgumentParser(description="Arr Studio repository preflight")
    parser.add_argument(
        "--phase",
        type=int,
        default=0,
        choices=sorted(REQUIRED_PHASE_FILES),
        help="highest implemented phase to validate (default: 0)",
    )
    args = parser.parse_args()
    phase = args.phase

    check_required_files(phase)
    check_env_safety()
    check_hacs()
    check_python(phase)
    version = check_const()
    if phase >= 2:
        check_manifest(version)
        check_translations()
    if phase >= 3:
        check_sensor_keys()
    if phase >= 4:
        check_payload_keys()
    if phase >= 5:
        check_png(PKG / "brand" / "icon.png", (256, 256))
        check_png(PKG / "brand" / "logo.png", (512, 256))
        check_frontend_security(phase)
    if phase >= 6:
        check_workflow()

    failures = 0
    for name, ok, detail in results:
        if ok:
            print(f"PASS {name}")
        else:
            failures += 1
            suffix = f" — {detail}" if detail else ""
            print(f"FAIL {name}{suffix}")

    print()
    if failures:
        print(f"preflight phase {phase}: {failures} failure(s)")
        return 1
    print(f"preflight phase {phase}: all {len(results)} checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
