import os
import re
import base64
import json
import time
import urllib.parse
import urllib.request
from flask import Flask, jsonify, request, send_from_directory

app = Flask(__name__)

CLIENT_ID = os.environ.get("SPOTIFY_CLIENT_ID", "c9d98c88c43f422380f7eae75fabbed6")
CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET", "0494fa1003cc4b1ea758f7c9fe3c65dd")

_token = {"value": None, "expires_at": 0}


def get_token():
    if _token["value"] and time.time() < _token["expires_at"] - 60:
        return _token["value"]
    refresh_token = os.environ.get("SPOTIFY_REFRESH_TOKEN", "")
    if not refresh_token:
        raise ValueError("SPOTIFY_REFRESH_TOKEN env var not set")
    creds = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    data = urllib.parse.urlencode({
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
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
    _token["value"] = payload["access_token"]
    _token["expires_at"] = time.time() + payload.get("expires_in", 3600)
    return _token["value"]


def extract_id(raw):
    m = re.search(r"playlist/([A-Za-z0-9]+)", raw)
    if m:
        return m.group(1)
    if re.fullmatch(r"[A-Za-z0-9]+", raw.strip()):
        return raw.strip()
    return None


def spotify_get(url, token):
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


@app.route("/")
def index():
    return send_from_directory(".", "spotify-to-bandcamp.html")


@app.route("/playlist")
def playlist():
    raw = request.args.get("url", "").strip()
    playlist_id = extract_id(raw)
    if not playlist_id:
        return jsonify({"error": "Could not parse playlist ID from input"}), 400

    try:
        token = get_token()
        pl = spotify_get(
            f"https://api.spotify.com/v1/playlists/{playlist_id}?fields=name",
            token,
        )
        tracks = []
        url = (
            f"https://api.spotify.com/v1/playlists/{playlist_id}/items"
            "?limit=50&fields=next,items(item(name,artists(name)))"
        )
        while url:
            page = spotify_get(url, token)
            for item in page.get("items") or []:
                track = item.get("item")
                if track and track.get("name"):
                    tracks.append({
                        "name": track["name"],
                        "artist": ", ".join(a["name"] for a in track.get("artists", [])),
                    })
            url = page.get("next")
        return jsonify({"name": pl.get("name", ""), "tracks": tracks})
    except urllib.error.HTTPError as e:
        if e.code == 403:
            return jsonify({"error": "This playlist is private. Open it in Spotify, go to ··· → Make public, then try again."}), 502
        if e.code == 404:
            return jsonify({"error": "Playlist not found. Check the URL and try again."}), 502
        body = e.read().decode()
        return jsonify({"error": f"Spotify error {e.code}: {body}"}), 502
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8888))
    app.run(host="0.0.0.0", port=port)
