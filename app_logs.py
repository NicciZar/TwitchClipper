import json
import os
import shutil
import sys
import threading
from datetime import datetime

_lock = threading.Lock()
_listeners = set()
_legacy_logs_migrated = False
_legacy_logs_migration_note = ""


def _base_dir() -> str:
    if getattr(sys, "frozen", False):
        local_appdata_root = os.getenv("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), "AppData", "Local")
        return os.path.join(local_appdata_root, "TwitchClipper")
    return os.path.dirname(os.path.abspath(__file__))


def _legacy_base_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def _migrate_legacy_logs_if_needed(target_logs_dir: str) -> None:
    global _legacy_logs_migrated, _legacy_logs_migration_note

    # Dev/source runs keep existing behavior; migration applies only to frozen builds.
    if not getattr(sys, "frozen", False):
        return
    if _legacy_logs_migrated:
        return

    legacy_logs_dir = os.path.join(_legacy_base_dir(), "logs")
    if os.path.abspath(legacy_logs_dir) == os.path.abspath(target_logs_dir):
        _legacy_logs_migrated = True
        return

    try:
        os.makedirs(target_logs_dir, exist_ok=True)
        migrated_files: list[str] = []
        for filename in ("session_actions.log", "clip_library.jsonl"):
            legacy_file = os.path.join(legacy_logs_dir, filename)
            target_file = os.path.join(target_logs_dir, filename)
            if os.path.exists(legacy_file) and not os.path.exists(target_file):
                shutil.copy2(legacy_file, target_file)
                migrated_files.append(filename)
        if migrated_files:
            _legacy_logs_migration_note = f"Legacy logs migrated from '{legacy_logs_dir}' to '{target_logs_dir}': {', '.join(migrated_files)}"
    except OSError:
        # Non-fatal: app continues and new logs are created in target directory.
        pass
    finally:
        _legacy_logs_migrated = True


def _logs_dir() -> str:
    path = os.path.join(_base_dir(), "logs")
    os.makedirs(path, exist_ok=True)
    _migrate_legacy_logs_if_needed(path)
    return path


def action_log_path() -> str:
    return os.path.join(_logs_dir(), "session_actions.log")


def clip_library_path() -> str:
    return os.path.join(_logs_dir(), "clip_library.jsonl")


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _read_clip_rows_unlocked(path: str) -> list[dict]:
    rows: list[dict] = []
    if not os.path.exists(path):
        return rows
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if str(row.get("clip_id", "")).strip():
                    rows.append(row)
    except OSError:
        return []
    return rows


def _write_clip_rows_unlocked(path: str, rows: list[dict]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=True) + "\n")


def _upsert_clip_record_unlocked(record: dict) -> None:
    path = clip_library_path()
    clip_id = str(record.get("clip_id", "")).strip()
    if not clip_id:
        return

    rows = _read_clip_rows_unlocked(path)
    replaced = False
    for idx, row in enumerate(rows):
        if str(row.get("clip_id", "")).strip() == clip_id:
            rows[idx] = record
            replaced = True
            break
    if not replaced:
        rows.append(record)
    _write_clip_rows_unlocked(path, rows)


def register_listener(callback) -> None:
    with _lock:
        _listeners.add(callback)


def unregister_listener(callback) -> None:
    with _lock:
        _listeners.discard(callback)


def _emit(event_type: str) -> None:
    with _lock:
        listeners = list(_listeners)
    for cb in listeners:
        try:
            cb(event_type)
        except Exception:
            pass


def start_session() -> None:
    try:
        with _lock:
            with open(action_log_path(), "w", encoding="utf-8") as f:
                f.write(f"Session started: {_now_iso()}\n")
                if _legacy_logs_migration_note:
                    f.write(f"[{_now_iso()}] Migration | {_legacy_logs_migration_note}\n")
        _emit("session")
    except OSError:
        pass


def log_action(action: str, details: str = "") -> None:
    try:
        line = f"[{_now_iso()}] {action}"
        if details:
            line += f" | {details}"
        with _lock:
            with open(action_log_path(), "a", encoding="utf-8") as f:
                f.write(line + "\n")
        _emit("session")
    except OSError:
        pass


def log_error(context: str, error_message: str) -> None:
    log_action("Error", f"{context}: {error_message}")


def log_clip_saved(
    clip_id: str,
    clip_url: str,
    file_path: str,
    title: str,
    broadcaster: str = "",
    game_name: str = "",
    broadcaster_id: str = "",
) -> None:
    record = {
        "saved_at": _now_iso(),
        "clip_id": clip_id,
        "clip_url": clip_url,
        "title": title,
        "broadcaster": broadcaster,
        "game_name": game_name,
        "broadcaster_id": broadcaster_id,
        "file_path": os.path.abspath(file_path),
        "status": "downloaded",
    }
    try:
        with _lock:
            _upsert_clip_record_unlocked(record)
        _emit("clip_library")
    except OSError:
        pass


def log_clip_pending(
    clip_id: str,
    clip_url: str,
    file_path: str,
    title: str,
    broadcaster: str = "",
    game_name: str = "",
    broadcaster_id: str = "",
) -> None:
    record = {
        "saved_at": _now_iso(),
        "clip_id": clip_id,
        "clip_url": clip_url,
        "title": title,
        "broadcaster": broadcaster,
        "game_name": game_name,
        "broadcaster_id": broadcaster_id,
        "file_path": os.path.abspath(file_path),
        "status": "missing",
    }
    try:
        with _lock:
            _upsert_clip_record_unlocked(record)
        _emit("clip_library")
    except OSError:
        pass


def log_clip_failed(
    clip_id: str,
    clip_url: str,
    file_path: str,
    title: str,
    error_message: str,
    broadcaster: str = "",
    game_name: str = "",
    broadcaster_id: str = "",
) -> None:
    record = {
        "saved_at": _now_iso(),
        "clip_id": clip_id,
        "clip_url": clip_url,
        "title": title,
        "broadcaster": broadcaster,
        "game_name": game_name,
        "broadcaster_id": broadcaster_id,
        "file_path": os.path.abspath(file_path),
        "status": "failed",
        "error": error_message,
    }
    try:
        with _lock:
            _upsert_clip_record_unlocked(record)
        _emit("clip_library")
    except OSError:
        pass


def log_clip_deleted(
    clip_id: str,
    clip_url: str,
    title: str,
    broadcaster: str = "",
    game_name: str = "",
    broadcaster_id: str = "",
    file_path: str = "",
) -> None:
    record = {
        "saved_at": _now_iso(),
        "clip_id": clip_id,
        "clip_url": clip_url,
        "title": title,
        "broadcaster": broadcaster,
        "game_name": game_name,
        "broadcaster_id": broadcaster_id,
        "file_path": os.path.abspath(file_path) if file_path else "",
        "status": "deleted",
    }
    try:
        with _lock:
            _upsert_clip_record_unlocked(record)
        _emit("clip_library")
    except OSError:
        pass


def purge_clip_library_entry(clip_id: str) -> bool:
    target = str(clip_id or "").strip()
    if not target:
        return False

    path = clip_library_path()
    try:
        with _lock:
            rows = _read_clip_rows_unlocked(path)
            filtered = [row for row in rows if str(row.get("clip_id", "")).strip() != target]
            if len(filtered) == len(rows):
                return False
            _write_clip_rows_unlocked(path, filtered)
        _emit("clip_library")
        return True
    except OSError:
        return False


def get_clip_library_entries() -> list[dict]:
    path = clip_library_path()
    if not os.path.exists(path):
        return []

    latest_by_clip_id: dict[str, dict] = {}
    ordered_ids: list[str] = []
    total_valid_rows = 0

    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                clip_id = str(row.get("clip_id", "")).strip()
                if not clip_id:
                    continue
                total_valid_rows += 1
                if clip_id not in latest_by_clip_id:
                    ordered_ids.append(clip_id)
                latest_by_clip_id[clip_id] = row
    except OSError:
        return []

    # Compact on-disk jsonl if duplicates were present.
    if total_valid_rows > len(ordered_ids):
        deduped_in_file_order = [latest_by_clip_id[cid] for cid in ordered_ids]
        try:
            with _lock:
                _write_clip_rows_unlocked(path, deduped_in_file_order)
        except OSError:
            pass

    # Newest first by record appearance.
    rows = [latest_by_clip_id[cid] for cid in reversed(ordered_ids)]
    for row in rows:
        if not row.get("status"):
            path = str(row.get("file_path", "")).strip()
            row["status"] = "downloaded" if path and os.path.exists(path) else "missing"
    return rows
