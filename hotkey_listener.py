import os
import re
import threading
import time

import keyboard

import app_logs
import config
import i18n
import tray
import twitch_api
import shutil


_current_hotkey: str = ""
_hotkey_handle = None
_lock = threading.Lock()


def _sanitize_segment(name: str, fallback: str) -> str:
    raw = (name or "").strip()
    if not raw:
        raw = fallback
    raw = re.sub(r'[\\/:*?"<>|]', "", raw)
    raw = re.sub(r"\s+", " ", raw).strip(" .")
    return raw or fallback


def _build_destination_path(cfg: dict, clip_title: str, broadcaster_name: str, game_name: str) -> str:
    root = cfg.get("download_folder", "")
    broadcaster_dir = _sanitize_segment(broadcaster_name, "unknown_broadcaster")
    game_dir = _sanitize_segment(game_name, "unknown_game")
    filename = _sanitize_segment(clip_title, "clip") + ".mp4"
    return os.path.join(root, broadcaster_dir, game_dir, filename)


def _api_call_with_refresh(cfg: dict, fn, *args, **kwargs):
    """Execute an API call with automatic token refresh on 401 errors."""
    client_id = cfg.get("client_id", "")
    client_secret = cfg.get("client_secret", "")
    try:
        return fn(*args, **kwargs)
    except PermissionError as exc:
        if "401" in str(exc) and client_secret and cfg.get("refresh_token"):
            try:
                new_tokens = twitch_api.refresh_access_token(
                    client_id, client_secret, cfg["refresh_token"]
                )
                cfg["access_token"] = new_tokens["access_token"]
                if new_tokens.get("refresh_token"):
                    cfg["refresh_token"] = new_tokens["refresh_token"]
                expires_in = int(new_tokens.get("expires_in", 0) or 0)
                cfg["token_expires_at"] = int(time.time()) + expires_in if expires_in > 0 else 0
                config.save(cfg)
                app_logs.log_action(i18n.t(cfg, "log_access_token_refreshed"))
                return fn(*args, **kwargs)
            except Exception as refresh_exc:
                raise PermissionError(f"Token refresh failed: {refresh_exc}") from refresh_exc
        raise


def try_refresh_token(cfg: dict) -> bool:
    """Attempt to refresh the access token if a refresh token is available.
    Returns True if refresh was successful, False otherwise."""
    client_id = cfg.get("client_id", "")
    client_secret = cfg.get("client_secret", "")
    refresh_token = cfg.get("refresh_token", "")
    
    if not all([client_id, client_secret, refresh_token]):
        return False
    
    try:
        new_tokens = twitch_api.refresh_access_token(
            client_id, client_secret, refresh_token
        )
        cfg["access_token"] = new_tokens["access_token"]
        if new_tokens.get("refresh_token"):
            cfg["refresh_token"] = new_tokens["refresh_token"]
        expires_in = int(new_tokens.get("expires_in", 0) or 0)
        cfg["token_expires_at"] = int(time.time()) + expires_in if expires_in > 0 else 0
        config.save(cfg)
        app_logs.log_action(i18n.t(cfg, "log_access_token_refreshed"))
        return True
    except Exception as exc:
        app_logs.log_error(i18n.t(cfg, "log_token_refresh"), str(exc))
        return False


def download_library_entry(entry: dict) -> tuple[bool, str]:
    cfg = config.load()
    token = cfg.get("access_token", "")
    client_id = cfg.get("client_id", "")
    clip_id = str(entry.get("clip_id", "")).strip()
    if not clip_id or not token or not client_id:
        return False, "Missing clip_id or auth configuration."

    broadcaster_id = str(cfg.get("broadcaster_id", "")).strip() or str(entry.get("broadcaster_id", "")).strip()
    broadcaster_name = str(cfg.get("broadcaster_name", "")).strip() or str(entry.get("broadcaster", "")).strip()
    game_name = str(entry.get("game_name", "")).strip()
    clip_title = str(entry.get("title", "")).strip() or clip_id
    clip_url = str(entry.get("clip_url", f"https://clips.twitch.tv/{clip_id}"))

    clip_meta: dict | None = None

    def _resolve_game_name(current_game_name: str) -> str:
        nonlocal clip_meta
        resolved = (current_game_name or "").strip()
        if resolved and resolved.lower() != "unknown_game":
            return resolved
        try:
            clip_meta = _api_call_with_refresh(cfg, twitch_api.poll_clip_ready, clip_id, cfg["access_token"], client_id)
            api_game_name = str(clip_meta.get("game_name", "")).strip()
            if api_game_name:
                return api_game_name
            game_id = str(clip_meta.get("game_id", "")).strip()
            if game_id:
                game_lookup = _api_call_with_refresh(cfg, twitch_api.get_game_names, [game_id], cfg["access_token"], client_id)
                looked_up = str(game_lookup.get(game_id, "")).strip()
                if looked_up:
                    return looked_up
        except Exception:
            pass
        return resolved

    game_name = _resolve_game_name(game_name)
    dest = _build_destination_path(cfg, clip_title, broadcaster_name, game_name)

    # Deduplication check and path correction
    existing_entry = next((row for row in app_logs.get_clip_library_entries() if row.get("clip_id") == clip_id), None)
    if existing_entry:
        existing_path = os.path.abspath(str(existing_entry.get("file_path", "")).strip())
        expected_path = os.path.abspath(dest)

        # Already in the right folder and still present on disk.
        if existing_path == expected_path and os.path.exists(expected_path):
            # Keep metadata normalized (e.g., broadcaster name) even on no-op re-downloads.
            app_logs.log_clip_saved(
                clip_id=clip_id,
                clip_url=clip_url,
                file_path=expected_path,
                title=clip_title,
                broadcaster=broadcaster_name,
                game_name=game_name,
                broadcaster_id=broadcaster_id,
            )
            return False, f"Clip '{clip_title}' has already been downloaded to {expected_path}."

        # Needs migration from old folder layout.
        if existing_path and existing_path != expected_path and os.path.exists(existing_path):
            try:
                os.makedirs(os.path.dirname(expected_path), exist_ok=True)
                shutil.move(existing_path, expected_path)
                app_logs.log_action("Moved clip file", f"{existing_path} -> {expected_path}")
                app_logs.log_clip_saved(
                    clip_id=clip_id,
                    clip_url=clip_url,
                    file_path=expected_path,
                    title=clip_title,
                    broadcaster=broadcaster_name,
                    game_name=game_name,
                    broadcaster_id=broadcaster_id,
                )
                return True, f"Clip '{clip_title}' has been moved to the correct folder."
            except Exception as exc:
                return False, f"Failed to move clip '{clip_title}' to the correct folder: {exc}"

        # Already present at expected path, but library pointed elsewhere.
        if os.path.exists(expected_path):
            app_logs.log_clip_saved(
                clip_id=clip_id,
                clip_url=clip_url,
                file_path=expected_path,
                title=clip_title,
                broadcaster=broadcaster_name,
                game_name=game_name,
                broadcaster_id=broadcaster_id,
            )
            return False, f"Clip '{clip_title}' has already been downloaded to {expected_path}."

    try:
        if clip_meta is None:
            _api_call_with_refresh(cfg, twitch_api.poll_clip_ready, clip_id, cfg["access_token"], client_id)
        logged_in_user = _api_call_with_refresh(cfg, twitch_api.get_logged_in_user, cfg["access_token"], client_id)
        editor_id = logged_in_user["id"]
        download_url = _api_call_with_refresh(
            cfg, twitch_api.get_clip_download_url, clip_id, broadcaster_id, editor_id, cfg["access_token"], client_id
        )
        app_logs.log_action(i18n.t(cfg, "log_downloading_clip"), dest)

        # Log folder creation
        folder_path = os.path.dirname(dest)
        if not os.path.exists(folder_path):
            app_logs.log_action(i18n.t(cfg, "log_creating_folder"), folder_path)

        _api_call_with_refresh(cfg, twitch_api.download_clip, download_url, dest)
        app_logs.log_action(i18n.t(cfg, "log_clip_downloaded"), dest)
        app_logs.log_clip_saved(
            clip_id=clip_id,
            clip_url=clip_url,
            file_path=dest,
            title=clip_title,
            broadcaster=broadcaster_name,
            game_name=game_name,
            broadcaster_id=broadcaster_id,
        )
        return True, dest
    except Exception as exc:
        app_logs.log_action(i18n.t(cfg, "log_downloading_clip"), f"Failed: {dest}")
        app_logs.log_clip_failed(
            clip_id=clip_id,
            clip_url=clip_url,
            file_path=dest,
            title=clip_title,
            error_message=str(exc),
            broadcaster=broadcaster_name,
            game_name=game_name,
            broadcaster_id=broadcaster_id,
        )
        return False, str(exc)


def delete_library_entry_on_twitch(entry: dict) -> tuple[bool, str]:
    cfg = config.load()
    token = cfg.get("access_token", "")
    client_id = cfg.get("client_id", "")
    clip_id = str(entry.get("clip_id", "")).strip()
    if not clip_id or not token or not client_id:
        return False, "Missing clip_id or auth configuration."

    clip_title = str(entry.get("title", "")).strip() or clip_id
    clip_url = str(entry.get("clip_url", f"https://clips.twitch.tv/{clip_id}"))
    broadcaster_name = str(entry.get("broadcaster", "")).strip() or cfg.get("broadcaster_name", "")
    game_name = str(entry.get("game_name", "")).strip()
    broadcaster_id = str(entry.get("broadcaster_id", "")).strip() or cfg.get("broadcaster_id", "")
    file_path = str(entry.get("file_path", "")).strip()

    try:
        app_logs.log_action(i18n.t(cfg, "log_deleting_clip"), clip_id)
        _api_call_with_refresh(cfg, twitch_api.delete_clip, clip_id, cfg["access_token"], client_id)
        app_logs.log_clip_deleted(
            clip_id=clip_id,
            clip_url=clip_url,
            title=clip_title,
            broadcaster=broadcaster_name,
            game_name=game_name,
            broadcaster_id=broadcaster_id,
            file_path=file_path,
        )
        return True, clip_id
    except Exception as exc:
        return False, str(exc)


def rename_library_entry_on_twitch(entry: dict, new_title: str) -> tuple[bool, str]:
    """Open the Twitch edit URL for a clip.
    Note: Twitch API does not support renaming clips programmatically.
    This function opens the web editor in the browser where the user can rename the clip."""
    cfg = config.load()
    clip_id = str(entry.get("clip_id", "")).strip()
    if not clip_id:
        return False, "Missing clip_id."

    try:
        import webbrowser
        edit_url = twitch_api.get_clip_edit_url(clip_id)
        webbrowser.open_new(edit_url)
        app_logs.log_action(
            i18n.t(cfg, "log_opening_clip_editor"),
            f"{clip_id}: {edit_url}",
        )
        return True, edit_url
    except Exception as exc:
        return False, str(exc)


def register(cfg: dict) -> None:
    global _current_hotkey, _hotkey_handle
    combo = cfg.get("hotkey", "").strip()
    if not combo:
        return
    with _lock:
        _unregister_current()
        try:
            _hotkey_handle = keyboard.add_hotkey(combo, _on_hotkey, suppress=False)
            _current_hotkey = combo
            app_logs.log_action(i18n.t(cfg, "log_hotkey_registered"), combo)
        except Exception as exc:
            tray.notify(
                i18n.t(cfg, "app_name"),
                i18n.t(cfg, "hotkey_register_failed", combo=combo, error=exc),
            )
            app_logs.log_error(i18n.t(cfg, "log_hotkey_registration"), str(exc))


def _unregister_current() -> None:
    global _hotkey_handle, _current_hotkey
    if _hotkey_handle is not None:
        try:
            keyboard.remove_hotkey(_hotkey_handle)
            app_logs.log_action(i18n.t(config.load(), "log_hotkey_unregistered"), _current_hotkey)
        except Exception:
            pass
        _hotkey_handle = None
        _current_hotkey = ""


def _on_hotkey() -> None:
    threading.Thread(target=_do_clip, daemon=True, name="clip-worker").start()


def _do_clip() -> None:
    cfg = config.load()

    token = cfg.get("access_token", "")
    client_id = cfg.get("client_id", "")
    broadcaster_id = cfg.get("broadcaster_id", "")
    broadcaster_name = cfg.get("broadcaster_name", "")
    duration = float(cfg.get("clip_duration", 30))
    template = cfg.get("clip_title_template", "{datetime}_{game}-{title}")
    auto_download = bool(cfg.get("auto_download", True))

    clip_id = ""
    clip_url = ""
    clip_title = ""
    stream = {"game_name": "", "title": ""}
    safe_dest = ""

    if not all([token, client_id, broadcaster_id]):
        tray.notify(i18n.t(cfg, "app_name"), i18n.t(cfg, "not_configured"))
        app_logs.log_error(i18n.t(cfg, "log_create_clip"), i18n.t(cfg, "log_create_clip_not_configured"))
        return

    def _api_call(fn, *args, **kwargs):
        return _api_call_with_refresh(cfg, fn, *args, **kwargs)

    try:
        tray.notify(i18n.t(cfg, "app_name"), i18n.t(cfg, "create_clip"))
        app_logs.log_action(i18n.t(cfg, "log_creating_clip"), f'broadcaster= "{broadcaster_name or broadcaster_id}"')

        # 1. Get stream info for title template
        try:
            stream = _api_call(
                twitch_api.get_stream_info, broadcaster_id, cfg["access_token"], client_id
            )
        except Exception:
            stream = {"game_name": "", "title": ""}

        # 2. Build title
        clip_title = twitch_api.build_clip_title(
            template,
            game=stream.get("game_name", ""),
            stream_title=stream.get("title", ""),
            broadcaster=broadcaster_name,
        )

        # 3. Create clip
        clip = _api_call(
            twitch_api.create_clip,
            broadcaster_id, cfg["access_token"], client_id,
            title=clip_title,
            duration=duration,
        )
        clip_id = clip["id"]
        clip_url = f"https://clips.twitch.tv/{clip_id}"
        app_logs.log_action(i18n.t(cfg, "log_clip_created"), f"clip_id={clip_id} link={clip_url}")

        safe_dest = _build_destination_path(
            cfg,
            clip_title,
            broadcaster_name,
            stream.get("game_name", ""),
        )

        if not auto_download:
            app_logs.log_clip_pending(
                clip_id=clip_id,
                clip_url=clip_url,
                file_path=safe_dest,
                title=clip_title,
                broadcaster=broadcaster_name,
                game_name=stream.get("game_name", ""),
                broadcaster_id=broadcaster_id,
            )
            tray.notify(i18n.t(cfg, "app_name"), i18n.t(cfg, "clip_created_no_download"))
            return

        tray.notify(i18n.t(cfg, "app_name"), i18n.t(cfg, "clip_created_prep"))

        # 4. Poll until ready
        _api_call(twitch_api.poll_clip_ready, clip_id, cfg["access_token"], client_id)

        # 5. Get download URL
        logged_in_user = _api_call(
            twitch_api.get_logged_in_user, cfg["access_token"], client_id
        )
        editor_id = logged_in_user["id"]

        download_url = _api_call(
            twitch_api.get_clip_download_url,
            clip_id, broadcaster_id, editor_id, cfg["access_token"], client_id,
        )

        # 6. Download file
        safe_filename = os.path.basename(safe_dest)
        dest = safe_dest
        tray.notify(i18n.t(cfg, "app_name"), i18n.t(cfg, "downloading_clip", name=safe_filename))
        app_logs.log_action(i18n.t(cfg, "log_downloading_clip"), dest)
        
        # Log folder creation
        folder_path = os.path.dirname(dest)
        if not os.path.exists(folder_path):
            app_logs.log_action(i18n.t(cfg, "log_creating_folder"), folder_path)
        
        _api_call(twitch_api.download_clip, download_url, dest)

        tray.notify(i18n.t(cfg, "app_name"), i18n.t(cfg, "clip_downloaded", name=safe_filename))
        app_logs.log_action(i18n.t(cfg, "log_clip_downloaded"), dest)
        app_logs.log_clip_saved(
            clip_id=clip_id,
            clip_url=clip_url,
            file_path=dest,
            title=clip_title,
            broadcaster=broadcaster_name,
            game_name=stream.get("game_name", ""),
            broadcaster_id=broadcaster_id,
        )

    except LookupError as exc:
        is_offline = str(exc).strip().lower() == "channel offline"
        broadcaster_label = (broadcaster_name or broadcaster_id or "broadcaster").strip()
        display_error = (
            i18n.t(cfg, "broadcaster_offline", broadcaster=broadcaster_label)
            if is_offline
            else str(exc)
        )
        if clip_id and auto_download:
            app_logs.log_clip_failed(
                clip_id=clip_id,
                clip_url=clip_url or f"https://clips.twitch.tv/{clip_id}",
                file_path=safe_dest or _build_destination_path(cfg, clip_title or clip_id, broadcaster_name, stream.get("game_name", "")),
                title=clip_title or clip_id,
                error_message=display_error,
                broadcaster=broadcaster_name,
                game_name=stream.get("game_name", ""),
                broadcaster_id=broadcaster_id,
            )
        tray.notify(i18n.t(cfg, "error_title"), display_error)
        if is_offline:
            app_logs.log_action(i18n.t(cfg, "log_broadcaster_offline", broadcaster=broadcaster_label))
        else:
            app_logs.log_error(i18n.t(cfg, "log_create_clip"), display_error)
    except PermissionError as exc:
        if clip_id and auto_download:
            app_logs.log_clip_failed(
                clip_id=clip_id,
                clip_url=clip_url or f"https://clips.twitch.tv/{clip_id}",
                file_path=safe_dest or _build_destination_path(cfg, clip_title or clip_id, broadcaster_name, stream.get("game_name", "")),
                title=clip_title or clip_id,
                error_message=str(exc),
                broadcaster=broadcaster_name,
                game_name=stream.get("game_name", ""),
                broadcaster_id=broadcaster_id,
            )
        tray.notify(i18n.t(cfg, "auth_error_title"), str(exc))
        app_logs.log_error(i18n.t(cfg, "log_create_clip_auth"), str(exc))
    except TimeoutError as exc:
        if clip_id and auto_download:
            app_logs.log_clip_failed(
                clip_id=clip_id,
                clip_url=clip_url or f"https://clips.twitch.tv/{clip_id}",
                file_path=safe_dest or _build_destination_path(cfg, clip_title or clip_id, broadcaster_name, stream.get("game_name", "")),
                title=clip_title or clip_id,
                error_message=str(exc),
                broadcaster=broadcaster_name,
                game_name=stream.get("game_name", ""),
                broadcaster_id=broadcaster_id,
            )
        tray.notify(i18n.t(cfg, "timeout_title"), str(exc))
        app_logs.log_error(i18n.t(cfg, "log_create_clip_timeout"), str(exc))
    except Exception as exc:
        if clip_id and auto_download:
            app_logs.log_clip_failed(
                clip_id=clip_id,
                clip_url=clip_url or f"https://clips.twitch.tv/{clip_id}",
                file_path=safe_dest or _build_destination_path(cfg, clip_title or clip_id, broadcaster_name, stream.get("game_name", "")),
                title=clip_title or clip_id,
                error_message=str(exc),
                broadcaster=broadcaster_name,
                game_name=stream.get("game_name", ""),
                broadcaster_id=broadcaster_id,
            )
        tray.notify(i18n.t(cfg, "error_title"), str(exc))
        app_logs.log_error(i18n.t(cfg, "log_create_clip_unexpected"), str(exc))
