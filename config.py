import json
import os
import shutil
import sys

_legacy_config_migrated = False
_legacy_clips_migration_note = ""


DEFAULTS = {
    "hotkey": "ctrl+shift+c",
    "broadcaster_name": "",
    "broadcaster_id": "",
    "client_id": "",
    "client_secret": "",
    "access_token": "",
    "refresh_token": "",
    "token_expires_at": 0,
    "clip_duration": 30,
    "clip_title_template": "{datetime}_{game}-{title}",
    "download_folder": "",
    "auto_download": True,
    "popup_enabled": True,
    "popup_display": 0,
    "popup_position": "bottom-right",
    "popup_opacity": 0.95,
    "popup_info_duration_ms": 3000,
    "popup_error_duration_ms": 6000,
    "language": "auto",
}


def _config_path() -> str:
    if getattr(sys, "frozen", False):
        appdata_root = os.getenv("APPDATA") or os.path.join(os.path.expanduser("~"), "AppData", "Roaming")
        base = os.path.join(appdata_root, "TwitchClipper")
        os.makedirs(base, exist_ok=True)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "config.json")


def _legacy_config_path() -> str:
    if getattr(sys, "frozen", False):
        legacy_base = os.path.dirname(sys.executable)
    else:
        legacy_base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(legacy_base, "config.json")


def _migrate_legacy_config_if_needed(target_path: str) -> None:
    global _legacy_config_migrated

    # Dev/source runs keep existing behavior; migration applies only to frozen builds.
    if not getattr(sys, "frozen", False):
        return
    if os.path.exists(target_path):
        return

    legacy_path = _legacy_config_path()
    if not os.path.exists(legacy_path):
        return

    try:
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        shutil.copy2(legacy_path, target_path)
        _legacy_config_migrated = True
    except OSError:
        # Non-fatal: app will continue with defaults if migration fails.
        pass


def consume_legacy_config_migrated_flag() -> bool:
    global _legacy_config_migrated
    migrated = _legacy_config_migrated
    _legacy_config_migrated = False
    return migrated


def consume_legacy_clips_migration_note() -> str:
    global _legacy_clips_migration_note
    note = _legacy_clips_migration_note
    _legacy_clips_migration_note = ""
    return note


def _default_download_folder() -> str:
    if getattr(sys, "frozen", False):
        videos_root = os.path.join(os.path.expanduser("~"), "Videos")
        preferred = os.path.join(videos_root, "TwitchClipper")
        if os.path.isdir(videos_root):
            return preferred
        local_appdata_root = os.getenv("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), "AppData", "Local")
        return os.path.join(local_appdata_root, "TwitchClipper", "clips")
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "clips")


def _legacy_default_download_folder() -> str:
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "clips")


def _migrate_legacy_download_folder_if_needed(data: dict) -> bool:
    global _legacy_clips_migration_note

    # Dev/source runs keep existing behavior; migration applies only to frozen builds.
    if not getattr(sys, "frozen", False):
        return False

    current = str(data.get("download_folder", "")).strip()
    if not current:
        data["download_folder"] = _default_download_folder()
        return True

    legacy_default = os.path.abspath(_legacy_default_download_folder())
    current_abs = os.path.abspath(current)
    if current_abs != legacy_default:
        return False

    new_default = os.path.abspath(_default_download_folder())
    if new_default == legacy_default:
        return False

    moved_any = False
    try:
        os.makedirs(new_default, exist_ok=True)

        if os.path.isdir(legacy_default):
            for name in os.listdir(legacy_default):
                src = os.path.join(legacy_default, name)
                dst = os.path.join(new_default, name)
                if os.path.exists(dst):
                    continue
                shutil.move(src, dst)
                moved_any = True

            try:
                if not os.listdir(legacy_default):
                    os.rmdir(legacy_default)
            except OSError:
                pass

        data["download_folder"] = new_default
        _legacy_clips_migration_note = (
            f"Legacy clip folder migrated from '{legacy_default}' to '{new_default}'"
            if moved_any
            else f"Download folder moved from '{legacy_default}' to '{new_default}'"
        )
        return True
    except OSError:
        # Non-fatal: keep old path if migration fails.
        data["download_folder"] = current_abs
        return False


def load() -> dict:
    path = _config_path()
    _migrate_legacy_config_if_needed(path)
    data = dict(DEFAULTS)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                stored = json.load(f)
            data.update(stored)
        except (json.JSONDecodeError, OSError):
            pass

    changed = _migrate_legacy_download_folder_if_needed(data)
    if not data.get("download_folder"):
        data["download_folder"] = _default_download_folder()
        changed = True

    if changed and getattr(sys, "frozen", False):
        try:
            save(data)
        except RuntimeError:
            pass
    return data


def save(data: dict) -> None:
    path = _config_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except OSError as e:
        raise RuntimeError(f"Failed to save config: {e}") from e
