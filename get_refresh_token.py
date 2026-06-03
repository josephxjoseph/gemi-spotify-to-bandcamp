import http.server
import urllib.parse
import urllib.request
import json
import base64
import webbrowser
import threading

CLIENT_ID = "c9d98c88c43f422380f7eae75fabbed6"
CLIENT_SECRET = "0494fa1003cc4b1ea758f7c9fe3c65dd"
REDIRECT_URI = "http://127.0.0.1:8888/callback"
SCOPES = "playlist-read-private playlist-read-collaborative"

_result = []
_server = None


class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/callback":
            self.send_response(404)
            self.end_headers()
            return

        params = urllib.parse.parse_qs(parsed.query)
        code = params.get("code", [None])[0]
        if not code:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"No code in callback")
            return

        creds = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
        data = urllib.parse.urlencode({
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
        }).encode()
        req = urllib.request.Request(
            "https://accounts.spotify.com/api/token",
            data=data,
            headers={
                "Authorization": f"Basic {creds}",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        with urllib.request.urlopen(req) as resp:
            payload = json.loads(resp.read())

        refresh_token = payload.get("refresh_token", "")
        _result.append(refresh_token)

        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(f"""<!DOCTYPE html>
<html><body style="font-family:sans-serif;padding:2rem;max-width:600px;">
<h2>Got it!</h2>
<p>Copy the token below and set it as <code>SPOTIFY_REFRESH_TOKEN</code>
in Render's Environment Variables:</p>
<textarea rows="4" style="width:100%;font-family:monospace;font-size:13px;padding:8px;">{refresh_token}</textarea>
<p style="color:#888;font-size:13px;">You can close this window.</p>
</body></html>""".encode())

        threading.Thread(target=_server.shutdown, daemon=True).start()


auth_url = "https://accounts.spotify.com/authorize?" + urllib.parse.urlencode({
    "client_id": CLIENT_ID,
    "response_type": "code",
    "redirect_uri": REDIRECT_URI,
    "scope": SCOPES,
})

print("Opening Spotify login in your browser...")
print(f"If it doesn't open automatically, visit:\n{auth_url}\n")
webbrowser.open(auth_url)

_server = http.server.HTTPServer(("127.0.0.1", 8888), Handler)
_server.serve_forever()

if _result:
    print(f"\nYour refresh token:\n{_result[0]}")
    print("\nSet this as SPOTIFY_REFRESH_TOKEN in Render's environment variables.")
