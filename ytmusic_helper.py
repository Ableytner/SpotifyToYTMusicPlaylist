import os.path

import Levenshtein
import requests
from ytmusicapi import YTMusic
from ytmusicapi.auth.oauth import OAuthCredentials, RefreshingToken

from spotify_helper import SpotifyTrack

class YTMusicHelper():
    def __init__(self) -> None:
        self._oauth_creds = OAuthCredentials(session=requests.Session())
        self._ytmusic = None

    def authorize(self) -> None:
        if not os.path.isfile("oauth.json"):
            RefreshingToken.prompt_for_token(self._oauth_creds, True, "oauth.json")
        
        self._ytmusic = YTMusic("oauth.json")

    def add_playlist(self, name: str, tracks: list[SpotifyTrack]) -> None:
        existing_playlists = self._ytmusic.get_library_playlists(None)

        for item in existing_playlists:
            if item["title"] == name:
                self._merge_playlists(item["playlistId"], tracks)
                return

        self._create_playlist(name, tracks)

    def _create_playlist(self, name: str, tracks: list[SpotifyTrack]) -> None:
        track_ids = []
        c = 0
        for track in tracks:
            track_id = self._find_track(track)
            if track_id is not None:
                track_ids.append(track_id)
                c += 1
                print(f"found {c} songs", end="\r")
            else:
                print(f"no matching version found for {track}")

        print(f"found {c} songs")

        # reverse to have newest songs at the top
        track_ids.reverse()

        self._ytmusic.create_playlist(name, "Playlist synchronized from Spotify", "PRIVATE", video_ids=track_ids)

        print(f"Created new playlist {name} with {len(track_ids)} songs")

    def _merge_playlists(self, playlist_id: str, tracks: list[SpotifyTrack]) -> None:
        pass

    def _find_track(self, track: SpotifyTrack) -> str:
        results = self._ytmusic.search(f"{track.title} {' '.join(track.artists)}", filter="songs", limit=10, ignore_spelling=True)

        results_with_dist = []
        for res in results:
            if res is None or "album" not in res.keys() or res["album"] is None or "name" not in res["album"]:
                continue

            title_dist = Levenshtein.distance(res["title"], track.title)
            album_dist = Levenshtein.distance(res["album"]["name"], track.album)

            artist_dist = 0
            for yt_artist in [item["name"] for item in res["artists"]]:
                curr_artist_lowest_dist = 999
                for sp_artist in track.artists:
                    dist = Levenshtein.distance(yt_artist, sp_artist, weights=(1, 1, 1))
                    if dist < curr_artist_lowest_dist:
                        curr_artist_lowest_dist = dist
                artist_dist += curr_artist_lowest_dist
            
            total_dist = title_dist * 2 \
                         + artist_dist * 2 \
                         + album_dist

            results_with_dist.append((total_dist, res["videoId"]))

        if len(results_with_dist) == 0:
            return None

        results_with_dist.sort(key=lambda x: x[0])

        if results_with_dist[0][0] > 50:
            return None

        return results_with_dist[0][1]
