import json
import os
import sys


DEFAULTS = {
    "hotkey": "ctrl+shift+c",
    "broadcaster_name": "",
    "broadcaster_id": "",
    "client_id": "",
    "client_secret": "",
    "access_token": "",
    "refresh_token": "",
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
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "config.json")


def _default_download_folder() -> str:
    if getattr(sys, "frozen", False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "clips")


def load() -> dict:
    path = _config_path()
    data = dict(DEFAULTS)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                stored = json.load(f)
            data.update(stored)
        except (json.JSONDecodeError, OSError):
            pass
    if not data.get("download_folder"):
        data["download_folder"] = _default_download_folder()
    return data


def save(data: dict) -> None:
    path = _config_path()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except OSError as e:
        raise RuntimeError(f"Failed to save config: {e}") from e
