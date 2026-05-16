from __future__ import annotations

import argparse
from datetime import datetime, timezone
import os
from pathlib import Path
import re
import subprocess
import sys

REPO = "NicciZar/TwitchClipper"
REPO_URL = "https://github.com/NicciZar/TwitchClipper"
EXE_PATH = Path("dist") / "TwitchClipper.exe"
RELEASE_NOTES_PATH = Path("build") / "release_notes.md"
SEMVER_TAG = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")


def run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, check=check, text=True, capture_output=True)


def run_stream(cmd: list[str], step: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    print(f"[release] {step}")
    completed = subprocess.run(cmd, check=False, text=True)
    if check and completed.returncode != 0:
        raise subprocess.CalledProcessError(completed.returncode, cmd)
    return completed


def ensure_tool_available(tool: str) -> None:
    probe = run([tool, "--version"], check=False)
    if probe.returncode != 0:
        raise RuntimeError(f"Required tool '{tool}' is not available on PATH.")


def git_status_clean() -> bool:
    out = run(["git", "status", "--porcelain"]).stdout.strip()
    return out == ""


def latest_semver_tag() -> tuple[int, int, int] | None:
    tags_output = run(["git", "tag", "--list", "v*", "--sort=-v:refname"]).stdout.splitlines()
    for tag in tags_output:
        m = SEMVER_TAG.match(tag.strip())
        if m:
            return int(m.group(1)), int(m.group(2)), int(m.group(3))
    return None


def _revision_range(last_tag: tuple[int, int, int] | None) -> str:
    if last_tag is None:
        return "HEAD"
    return f"v{last_tag[0]}.{last_tag[1]}.{last_tag[2]}..HEAD"


def commit_messages_since(last_tag: tuple[int, int, int] | None) -> list[str]:
    rev_range = _revision_range(last_tag)
    out = run(["git", "log", "--format=%s%n%b", rev_range]).stdout
    return [line.strip() for line in out.splitlines() if line.strip()]


def commits_since(last_tag: tuple[int, int, int] | None) -> list[tuple[str, str]]:
    rev_range = _revision_range(last_tag)
    out = run(["git", "log", "--format=%h%x09%s", rev_range]).stdout
    items: list[tuple[str, str]] = []
    for line in out.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t", 1)
        if len(parts) == 2:
            items.append((parts[0].strip(), parts[1].strip()))
    return items


def classify_bump(messages: list[str]) -> str | None:
    if not messages:
        return None

    text = "\n".join(messages)
    if "BREAKING CHANGE" in text:
        return "major"

    for line in messages:
        if re.match(r"^[a-zA-Z]+\(.+\)!:", line) or re.match(r"^[a-zA-Z]+!:", line):
            return "major"

    if any(line.lower().startswith("feat") for line in messages):
        return "minor"

    return "patch"


def bump_version(base: tuple[int, int, int], bump: str) -> tuple[int, int, int]:
    major, minor, patch = base
    if bump == "major":
        return major + 1, 0, 0
    if bump == "minor":
        return major, minor + 1, 0
    return major, minor, patch + 1


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def current_short_commit() -> str:
    return run(["git", "rev-parse", "--short", "HEAD"]).stdout.strip() or "unknown"


def write_release_notes(version: str, build_date: str, bump: str, commits: list[tuple[str, str]]) -> None:
    RELEASE_NOTES_PATH.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"# v{version}",
        "",
        f"- Build date: {build_date}",
        f"- Bump type: {bump}",
        f"- Repository: {REPO_URL}",
        "",
        "## Included commits",
    ]
    for short_sha, subject in commits:
        lines.append(f"- {short_sha} {subject}")
    lines.append("")
    RELEASE_NOTES_PATH.write_text("\n".join(lines), encoding="utf-8")


def generate_version_files(version: str, build_date: str, commit_hash: str, python_runtime: str) -> None:
    print(f"[release] Generating version metadata for v{version} ({build_date})")
    cmd = [
        sys.executable,
        "scripts/generate_version_files.py",
        "--version",
        version,
        "--build-date",
        build_date,
        "--repo-url",
        REPO_URL,
        "--author",
        "NicciZar",
        "--license",
        "MIT",
        "--homepage-url",
        REPO_URL,
        "--issues-url",
        f"{REPO_URL}/issues",
        "--commit-hash",
        commit_hash,
        "--build-type",
        "release",
        "--python-runtime",
        python_runtime,
        "--out-version-py",
        "app_version.py",
        "--out-pyinstaller",
        "build/version_info.txt",
    ]
    run(cmd)


def build_exe(version: str, build_date: str, commit_hash: str, python_runtime: str) -> None:
    print(f"[release] Building executable for v{version}")
    env = dict(**os.environ)
    env["APP_VERSION"] = version
    env["APP_BUILD_DATE"] = build_date
    env["APP_REPO_URL"] = REPO_URL
    env["APP_HOMEPAGE_URL"] = REPO_URL
    env["APP_ISSUES_URL"] = f"{REPO_URL}/issues"
    env["APP_AUTHOR"] = "NicciZar"
    env["APP_LICENSE"] = "MIT"
    env["APP_BUILD_TYPE"] = "release"
    env["APP_COMMIT_HASH"] = commit_hash
    env["APP_PYTHON_RUNTIME"] = python_runtime
    subprocess.run(["cmd", "/c", "build.bat"], check=True, text=True, env=env)


def maybe_commit_release_files(version: str) -> None:
    print("[release] Checking if release metadata needs a commit")
    run(["git", "add", "app_version.py"])
    diff = run(["git", "diff", "--cached", "--name-only"]).stdout.strip()
    if diff:
        run_stream(["git", "commit", "-m", f"chore(release): v{version}"], "Committing updated app_version.py")
    else:
        print("[release] No metadata changes to commit")


def create_and_push_tag(version: str) -> None:
    tag = f"v{version}"
    run_stream(["git", "tag", tag], f"Creating tag {tag}")
    run_stream(["git", "push"], "Pushing branch commits")
    run_stream(["git", "push", "origin", tag], f"Pushing tag {tag}")


def create_github_release(version: str) -> None:
    tag = f"v{version}"
    run_stream(
        [
            "gh",
            "release",
            "create",
            tag,
            str(EXE_PATH),
            "--repo",
            REPO,
            "--title",
            tag,
            "--notes-file",
            str(RELEASE_NOTES_PATH),
        ],
        f"Creating GitHub Release {tag} and uploading {EXE_PATH}",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Build and publish a GitHub release with semantic versioning.")
    parser.add_argument("--dry-run", action="store_true", help="Compute and print next version only.")
    args = parser.parse_args()

    ensure_tool_available("git")
    ensure_tool_available("gh")
    print("[release] Tools OK: git, gh")

    last = latest_semver_tag() or (0, 0, 0)
    previous_tag = None if last == (0, 0, 0) else last
    messages = commit_messages_since(previous_tag)
    commit_entries = commits_since(previous_tag)
    bump = classify_bump(messages)
    if bump is None:
        raise RuntimeError("No commits found to release.")

    next_version = bump_version(last, bump)
    version_str = f"{next_version[0]}.{next_version[1]}.{next_version[2]}"
    print(f"[release] Bump type: {bump}")
    print(f"[release] Next version: v{version_str}")
    print(f"[release] Commits since last tag: {len(commit_entries)}")

    if args.dry_run:
        print(version_str)
        return 0

    if not git_status_clean():
        raise RuntimeError("Working tree is not clean. Commit or stash changes before release.")

    build_date = now_utc()
    commit_hash = current_short_commit()
    python_runtime = f"Python {sys.version.split()[0]}"
    print(f"[release] Commit hash: {commit_hash}")
    print(f"[release] Python runtime: {python_runtime}")
    write_release_notes(version_str, build_date, bump, commit_entries)
    print(f"[release] Release notes written: {RELEASE_NOTES_PATH}")
    generate_version_files(version_str, build_date, commit_hash, python_runtime)
    maybe_commit_release_files(version_str)
    build_exe(version_str, build_date, commit_hash, python_runtime)

    if not EXE_PATH.exists():
        raise RuntimeError(f"Build succeeded but executable was not found at '{EXE_PATH}'.")

    create_and_push_tag(version_str)
    create_github_release(version_str)

    print(f"Release complete: v{version_str}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
