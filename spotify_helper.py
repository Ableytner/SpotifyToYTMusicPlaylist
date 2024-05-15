import base64
from dataclasses import dataclass
import http.server
import http
from socketserver import BaseRequestHandler
import string
import random
from typing import Any, Callable, Self
import urllib.parse
import requests
import urllib
import webbrowser
from configparser import SectionProxy
from datetime import datetime, timedelta
from time import sleep

@dataclass
class SpotifyTrack:
    title: str
    artists: list[str]
    album: str

    def __str__(self) -> str:
        return f"{', '.join(self.artists)} - {self.title}"

class SpotifyHelper():
    def __init__(self, config: SectionProxy) -> None:
        self._config = config
        self._auth_state = None
        self._access_token = None
        self._refresh_token = None
        self._token_timeout = None

    def authorize(self):
        self._auth_state = "".join([random.choice(string.ascii_letters + string.digits) for _ in range(16)])
        url = "https://accounts.spotify.com/authorize?"
        params = {
            "response_type": "code",
            "client_id": self._config["client_id"],
            "scope": "playlist-read-private playlist-read-collaborative user-library-read",
            "state": self._auth_state,
            "redirect_uri": "http://localhost:8888/spotify_auth"
        }
        url_with_params = url + urllib.parse.urlencode(params)

        browser = webbrowser.get()
        browser.open(url_with_params)
        
        self._run_http_server()

        while self._token_timeout is None:
            sleep(1)
        
        assert self._access_token is not None
        assert self._refresh_token is not None
    
    def get_playlist(self, playlist_id: str) -> tuple[str, list[SpotifyTrack]]:
        url = f"https://api.spotify.com/v1/playlists/{playlist_id}"
        headers = {
            "Authorization": f"Bearer {self._access_token}"
        }
        params = {
            "fields": "name,tracks.total"
        }

        res = requests.get(url, headers=headers)

        if "error" in res.json():
            raise Exception(f"received error: {res.json()}")

        playlist_name = res.json()["name"]
        total_tracks = res.json()["tracks"]["total"]
        print(f"Requesting {total_tracks} tracks from playlist {playlist_name}")

        tracks = []
        offset = 0
        while offset < total_tracks:
            tracks += self._get_tracks_from_playlist(playlist_id, offset, 100)
            offset += 100
            print(f"Retrieved {len(tracks)} tracks", end="\r")

        print(f"Retrieved {len(tracks)} tracks")

        return (playlist_name, tracks)

    def _get_tracks_from_playlist(self, playlist_id: str, offset: int, limit: int) -> list[SpotifyTrack]:
        url = f"https://api.spotify.com/v1/playlists/{playlist_id}/tracks"
        headers = {
            "Authorization": f"Bearer {self._access_token}"
        }
        params = {
            "offset": offset,
            "limit": limit,
            "fields": "items(track(name,album,artists))"
        }

        res = requests.get(url, headers=headers, params=params)

        if "error" in res.json():
            raise Exception(f"received error: {res.json()}")

        tracks = []
        for track in [item["track"] for item in res.json()["items"]]:
            tracks.append(SpotifyTrack(track["name"], [item["name"] for item in track['artists']], track["album"]["name"]))
        
        return tracks

    def _run_http_server(self):
        server_address = ("", 8888)
        with self._HTTPServer(self._handle_auth_redirect, server_address, self._HTTPRequestHandler) as httpd:
            httpd.timeout = None
            httpd.handle_request()
    
    def _handle_auth_redirect(self, auth_code: str, state: str):
        if state != self._auth_state:
            raise Exception("Authentication states did not match")
        
        url = "https://accounts.spotify.com/api/token"
        authorization = f"{self._config['client_id']}:{self._config['client_secret']}"
        authorization_encoded = base64.b64encode(authorization.encode("ascii")).decode("ascii")
        headers = {
            "content-type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {authorization_encoded}"
        }
        params = {
            "grant_type": "authorization_code",
            "code": auth_code,
            "redirect_uri": "http://localhost:8888/spotify_auth"
        }

        res = requests.post(url, headers=headers, params=params)

        if "error" in res.json():
            raise Exception(f"received error: {res.json()}")
        
        self._access_token = res.json()["access_token"]
        self._refresh_token = res.json()["refresh_token"]
        self._token_timeout = datetime.now() + timedelta(seconds=res.json()["expires_in"])
        self._auth_state = None

    class _HTTPServer(http.server.HTTPServer):
        def __init__(self, request_callback, server_address: tuple[str | bytes | bytearray, int], RequestHandlerClass: Callable[[Any, Any, Self], BaseRequestHandler], bind_and_activate: bool = True) -> None:
            super().__init__(server_address, RequestHandlerClass, bind_and_activate)
            self.request_callback = request_callback

    class _HTTPRequestHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if not self.path.startswith("/spotify_auth"):
                print(f"request to unsupported endpoint {self.path.split("?", maxsplit=1)[0]}")

            params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            auth_code = params["code"][0]
            state = params["state"][0]

            self.close_connection = True
            self.send_response(200)

            self.server.request_callback(auth_code, state)
