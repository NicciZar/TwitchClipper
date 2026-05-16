import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

import requests

TOKEN_URL = "https://id.twitch.tv/oauth2/token"
AUTH_URL = "https://id.twitch.tv/oauth2/authorize"
VALIDATE_URL = "https://id.twitch.tv/oauth2/validate"
SCOPES = "clips:edit channel:manage:clips"
REDIRECT_PORT = 3000
REDIRECT_URI = f"http://localhost:{REDIRECT_PORT}"


# ---------------------------------------------------------------------------
# OAuth browser flow
# ---------------------------------------------------------------------------

def start_oauth_browser_flow(client_id: str, client_secret: str) -> dict:
    """Open Twitch OAuth in browser, capture the code via local server,
    exchange for tokens. Returns {"access_token": ..., "refresh_token": ...}"""

    result: dict = {}
    error_holder: list = []
    server_ready = threading.Event()
    done = threading.Event()

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            if "code" in params:
                code = params["code"][0]
                try:
                    tokens = _exchange_code(code, client_id, client_secret)
                    result.update(tokens)
                except Exception as exc:
                    error_holder.append(str(exc))
                self._send_html(
                    "<h2>TwitchClipper: Login successful!</h2>"
                    "<p>You may close this tab.</p>"
                )
            elif "error" in params:
                error_holder.append(params.get("error_description", ["Unknown error"])[0])
                self._send_html(
                    "<h2>TwitchClipper: Login failed.</h2>"
                    f"<p>{error_holder[-1]}</p>"
                )
            else:
                self._send_html("<h2>TwitchClipper</h2><p>No code received.</p>")
            done.set()

        def _send_html(self, body: str):
            html = f"<html><body>{body}</body></html>".encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)

        def log_message(self, *args):  # suppress server log output
            pass

    def _run_server():
        srv = HTTPServer(("localhost", REDIRECT_PORT), _Handler)
        server_ready.set()
        srv.handle_request()
        srv.server_close()

    t = threading.Thread(target=_run_server, daemon=True)
    t.start()
    server_ready.wait(timeout=3)

    auth_params = {
        "client_id": client_id,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPES,
        "force_verify": "true",
    }
    url = AUTH_URL + "?" + urllib.parse.urlencode(auth_params)
    webbrowser.open(url)

    done.wait(timeout=120)
    if error_holder:
        raise RuntimeError(f"OAuth error: {error_holder[0]}")
    if not result:
        raise TimeoutError("OAuth login timed out or was not completed.")
    return result


def _exchange_code(code: str, client_id: str, client_secret: str) -> dict:
    resp = requests.post(
        TOKEN_URL,
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": REDIRECT_URI,
        },
        timeout=15,
    )
    resp.raise_for_status()
    body = resp.json()
    return {
        "access_token": body["access_token"],
        "refresh_token": body.get("refresh_token", ""),
        "expires_in": int(body.get("expires_in", 0) or 0),
    }


# ---------------------------------------------------------------------------
# Manual token validation
# ---------------------------------------------------------------------------

def validate_manual_token(token: str, client_id: str) -> dict:
    """Validate a manually supplied token. Returns user info dict on success,
    raises on failure."""
    resp = requests.get(
        VALIDATE_URL,
        headers={"Authorization": f"OAuth {token}"},
        timeout=10,
    )
    if resp.status_code == 401:
        raise PermissionError("Token is invalid or expired.")
    resp.raise_for_status()
    validation = resp.json()
    scopes = validation.get("scopes", [])
    required = {"clips:edit", "channel:manage:clips"}
    missing = required - set(scopes)
    if missing:
        raise PermissionError(
            f"Token is missing required scopes: {', '.join(missing)}"
        )
    return validation
