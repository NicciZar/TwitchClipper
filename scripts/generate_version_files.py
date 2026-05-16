from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path
import re

DEFAULT_REPO_URL = "https://github.com/NicciZar/TwitchClipper"


def _normalize_semver(version: str) -> tuple[int, int, int, str]:
    raw = (version or "").strip()
    if raw.startswith("v"):
        raw = raw[1:]

    # Keep optional prerelease/build suffix for display, but only numeric core for EXE version fields.
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)(.*)$", raw)
    if not match:
        return 0, 0, 0, "0.0.0-dev"

    major = int(match.group(1))
    minor = int(match.group(2))
    patch = int(match.group(3))
    suffix = (match.group(4) or "").strip()
    display = f"{major}.{minor}.{patch}{suffix}"
    return major, minor, patch, display


def _default_build_date() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _write_app_version_file(path: Path, version: str, build_date: str, repo_url: str) -> None:
    content = (
        '"""Application build metadata.\n'
        "This file can be updated automatically by release scripts.\"\"\"\n\n"
        'APP_NAME = "TwitchClipper"\n'
        f'APP_VERSION = "{version}"\n'
        f'APP_BUILD_DATE = "{build_date}"\n'
        f'APP_REPO_URL = "{repo_url}"\n'
    )
    path.write_text(content, encoding="utf-8")


def _write_pyinstaller_version_file(path: Path, version_display: str, major: int, minor: int, patch: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    file_content = f'''# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({major}, {minor}, {patch}, 0),
    prodvers=({major}, {minor}, {patch}, 0),
    mask=0x3F,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
        StringTable(
          u'040904B0',
          [
            StringStruct(u'CompanyName', u''),
            StringStruct(u'FileDescription', u'TwitchClipper'),
            StringStruct(u'FileVersion', u'{version_display}'),
            StringStruct(u'InternalName', u'TwitchClipper'),
            StringStruct(u'LegalCopyright', u''),
            StringStruct(u'OriginalFilename', u'TwitchClipper.exe'),
            StringStruct(u'ProductName', u'TwitchClipper'),
            StringStruct(u'ProductVersion', u'{version_display}')
          ]
        )
      ]
    ),
    VarFileInfo([VarStruct(u'Translation', [1033, 1200])])
  ]
)
'''
    path.write_text(file_content, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate app metadata and PyInstaller version files.")
    parser.add_argument("--version", default="0.0.0-dev")
    parser.add_argument("--build-date", default="")
    parser.add_argument("--repo-url", default=DEFAULT_REPO_URL)
    parser.add_argument("--out-version-py", default="app_version.py")
    parser.add_argument("--out-pyinstaller", default="build/version_info.txt")
    args = parser.parse_args()

    major, minor, patch, display_version = _normalize_semver(args.version)
    build_date = args.build_date.strip() or _default_build_date()

    _write_app_version_file(Path(args.out_version_py), display_version, build_date, args.repo_url)
    _write_pyinstaller_version_file(Path(args.out_pyinstaller), display_version, major, minor, patch)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
