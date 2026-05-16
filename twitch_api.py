import os
import re
import time
from datetime import datetime

import requests

HELIX = "https://api.twitch.tv/helix"


def _headers(token: str, client_id: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Client-Id": client_id,
    }


def _raise_for(resp: requests.Response) -> None:
    if resp.status_code == 401:
        raise PermissionError("401: Token invalid or missing scope.")
    if resp.status_code == 403:
        raise PermissionError(f"403: Access denied. {resp.text}")
    if resp.status_code == 404:
        body_text = (resp.text or "").lower()
        if "channel offline" in body_text:
            raise LookupError("channel offline")
        raise LookupError(f"404: Not found. {resp.text}")
    resp.raise_for_status()


# ---------------------------------------------------------------------------
# Users / broadcaster resolution
# ---------------------------------------------------------------------------

def get_broadcaster_id(name: str, token: str, client_id: str) -> str:
    resp = requests.get(
        f"{HELIX}/users",
        params={"login": name.lower().strip()},
        headers=_headers(token, client_id),
        timeout=10,
    )
    _raise_for(resp)
    data = resp.json().get("data", [])
    if not data:
        raise LookupError(f"Broadcaster '{name}' not found.")
    return data[0]["id"]


def get_logged_in_user(token: str, client_id: str) -> dict:
    resp = requests.get(
        f"{HELIX}/users",
        headers=_headers(token, client_id),
        timeout=10,
    )
    _raise_for(resp)
    data = resp.json().get("data", [])
    if not data:
        raise LookupError("Could not retrieve logged-in user.")
    return data[0]


# ---------------------------------------------------------------------------
# Stream info
# ---------------------------------------------------------------------------

def get_stream_info(broadcaster_id: str, token: str, client_id: str) -> dict:
    resp = requests.get(
        f"{HELIX}/streams",
        params={"user_id": broadcaster_id},
        headers=_headers(token, client_id),
        timeout=10,
    )
    _raise_for(resp)
    data = resp.json().get("data", [])
    if not data:
        return {"game_name": "", "title": ""}
    return {"game_name": data[0].get("game_name", ""), "title": data[0].get("title", "")}


# ---------------------------------------------------------------------------
# Clip title helpers
# ---------------------------------------------------------------------------

def _sanitize(s: str, max_len: int = 140) -> str:
    s = re.sub(r'[\\/:*?"<>|]', "", s)
    s = s.strip()
    return s[:max_len]


def build_clip_title(template: str, game: str, stream_title: str, broadcaster: str) -> str:
    now = datetime.now()
    result = template.replace("{datetime}", now.strftime("%Y%m%d_%H%M%S"))
    result = result.replace("{date}", now.strftime("%Y%m%d"))
    result = result.replace("{time}", now.strftime("%H%M%S"))
    result = result.replace("{game}", game or "")
    result = result.replace("{title}", stream_title or "")
    result = result.replace("{broadcaster}", broadcaster or "")
    result = re.sub(r"[-_]{2,}", lambda m: m.group(0)[0], result)
    result = result.strip("-_ ")
    return _sanitize(result) or datetime.now().strftime("%Y%m%d_%H%M%S")


# ---------------------------------------------------------------------------
# Clip creation
# ---------------------------------------------------------------------------

def create_clip(
    broadcaster_id: str,
    token: str,
    client_id: str,
    title: str = "",
    duration: float = 30,
) -> dict:
    params = {
        "broadcaster_id": broadcaster_id,
        "has_delay": "false",
        "duration": duration,
    }
    if title:
        params["title"] = title
    resp = requests.post(
        f"{HELIX}/clips",
        params=params,
        headers=_headers(token, client_id),
        timeout=15,
    )
    _raise_for(resp)
    data = resp.json().get("data", [])
    if not data:
        raise RuntimeError("Clip creation returned no data.")
    return data[0]  # {"id": ..., "edit_url": ...}


# ---------------------------------------------------------------------------
# Polling
# ---------------------------------------------------------------------------

def poll_clip_ready(
    clip_id: str,
    token: str,
    client_id: str,
    timeout: int = 20,
    interval: float = 2.0,
) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        resp = requests.get(
            f"{HELIX}/clips",
            params={"id": clip_id},
            headers=_headers(token, client_id),
            timeout=10,
        )
        _raise_for(resp)
        data = resp.json().get("data", [])
        if data:
            return data[0]
        time.sleep(interval)
    raise TimeoutError(f"Clip {clip_id} was not ready within {timeout}s.")


# ---------------------------------------------------------------------------
# Download URL
# ---------------------------------------------------------------------------

def get_clip_download_url(
    clip_id: str,
    broadcaster_id: str,
    editor_id: str,
    token: str,
    client_id: str,
) -> str:
    resp = requests.get(
        f"{HELIX}/clips/downloads",
        params={
            "broadcaster_id": broadcaster_id,
            "editor_id": editor_id,
            "clip_id": clip_id,
        },
        headers=_headers(token, client_id),
        timeout=10,
    )
    _raise_for(resp)
    data = resp.json().get("data", [])
    if not data:
        raise LookupError("No download URL returned for clip.")
    url = data[0].get("landscape_download_url") or data[0].get("portrait_download_url")
    if not url:
        raise LookupError("Download URL is null (clip may not be downloadable).")
    return url


# ---------------------------------------------------------------------------
# Clip deletion
# ---------------------------------------------------------------------------

def delete_clip(clip_id: str, token: str, client_id: str) -> None:
    resp = requests.delete(
        f"{HELIX}/clips",
        params={"id": clip_id},
        headers=_headers(token, client_id),
        timeout=10,
    )
    _raise_for(resp)


# ---------------------------------------------------------------------------
# Clip editing
# ---------------------------------------------------------------------------

def get_clip_edit_url(clip_id: str) -> str:
    """Get the Twitch web edit URL for a clip.
    Note: Twitch API does not support renaming clips programmatically.
    Editing must be done through the web interface."""
    return f"https://www.twitch.tv/popout/{clip_id}/edit"


# ---------------------------------------------------------------------------
# Get all clips for broadcaster
# ---------------------------------------------------------------------------

def get_game_names(
    game_ids: list,
    token: str,
    client_id: str,
) -> dict:
    """
    Fetch game names for a list of game_ids.
    Returns a dict mapping game_id -> game_name.
    """
    if not game_ids:
        return {}
    
    game_id_to_name = {}
    # Process in batches of 100 (Twitch API limit)
    for i in range(0, len(game_ids), 100):
        batch = game_ids[i:i+100]
        resp = requests.get(
            f"{HELIX}/games",
            params={"id": batch},
            headers=_headers(token, client_id),
            timeout=10,
        )
        _raise_for(resp)
        data = resp.json().get("data", [])
        for game in data:
            game_id_to_name[game.get("id", "")] = game.get("name", "")
    
    return game_id_to_name


def get_broadcaster_clips(
    broadcaster_id: str,
    token: str,
    client_id: str,
    limit: int = 100,
) -> list:
    """
    Fetch all clips for a broadcaster from Twitch Helix API with game names.
    
    Returns a list of clip dicts with all available fields from the API response,
    including: clip_id, title, creator_name, created_at, url, view_count, thumbnail_url, game_id, game_name, language, video_id
    Automatically paginates through all results and looks up game names.
    """
    clips = []
    after = None
    
    while True:
        params = {
            "broadcaster_id": broadcaster_id,
            "first": min(limit, 100),  # Twitch max is 100 per request
        }
        if after:
            params["after"] = after
        
        resp = requests.get(
            f"{HELIX}/clips",
            params=params,
            headers=_headers(token, client_id),
            timeout=10,
        )
        _raise_for(resp)
        
        data = resp.json().get("data", [])
        if not data:
            break
        
        for clip in data:
            clips.append({
                "clip_id": clip.get("id", ""),
                "title": clip.get("title", ""),
                "creator_name": clip.get("creator_name", ""),
                "created_at": clip.get("created_at", ""),
                "url": clip.get("url", ""),
                "view_count": clip.get("view_count", 0),
                "thumbnail_url": clip.get("thumbnail_url", ""),
                "game_id": clip.get("game_id", ""),
                "language": clip.get("language", ""),
                "video_id": clip.get("video_id", ""),
                "broadcaster_id": clip.get("broadcaster_id", ""),
            })
        
        # Check for pagination
        pagination = resp.json().get("pagination", {})
        after = pagination.get("cursor")
        if not after:
            break
    
    # Fetch game names for all unique game_ids
    unique_game_ids = list(set(clip.get("game_id", "") for clip in clips if clip.get("game_id")))
    game_id_to_name = {}
    if unique_game_ids:
        try:
            game_id_to_name = get_game_names(unique_game_ids, token, client_id)
        except Exception:
            # If game name lookup fails, continue without game names
            pass
    
    # Add game_name to each clip
    for clip in clips:
        game_id = clip.get("game_id", "")
        clip["game_name"] = game_id_to_name.get(game_id, "")
    
    return clips


# ---------------------------------------------------------------------------
# File download
# ---------------------------------------------------------------------------

def download_clip(url: str, dest_path: str) -> None:
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    with requests.get(url, stream=True, timeout=60) as resp:
        resp.raise_for_status()
        with open(dest_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=65536):
                if chunk:
                    f.write(chunk)


# ---------------------------------------------------------------------------
# Token refresh
# ---------------------------------------------------------------------------

def refresh_access_token(
    client_id: str,
    client_secret: str,
    refresh_token: str,
) -> dict:
    resp = requests.post(
        "https://id.twitch.tv/oauth2/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()  # {"access_token": ..., "refresh_token": ...}
