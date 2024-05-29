import os.path

import Levenshtein
import requests
from ytmusicapi import YTMusic
from ytmusicapi.auth.oauth import OAuthCredentials, RefreshingToken

from track import BaseTrack, SpotifyTrack, YtMusicTrack

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
            found_track = self._find_track(track)
            if found_track is not None:
                track_ids.append(found_track.video_id)
                c += 1
                print(f"found {c} songs", end="\r")
                # print(track)
                # print(f"found {found_track}")
            else:
                print(f"no matching version found for {track}")

        print(f"found {c} songs")

        if c == 0:
            print("aborting...")
            return

        # reverse to have newest songs at the top
        track_ids.reverse()

        self._ytmusic.create_playlist(name, "Playlist synchronized from Spotify", "PRIVATE", video_ids=track_ids)
        print(f"Created new playlist {name} with {len(track_ids)} songs")

    def _merge_playlists(self, playlist_id: str, tracks: list[SpotifyTrack]) -> None:
        pass

    def _find_track(self, sp_track: SpotifyTrack) -> YtMusicTrack | None:
        results = self._ytmusic.search(f"{sp_track.title} {' '.join(sp_track.artists)}", filter="songs", limit=10, ignore_spelling=True)

        closest_track = None
        closest_track_dist = 999
        for res in results:
            yt_track = YtMusicTrack.from_response(res)
            if yt_track is None:
                continue

            dist = self._track_dist(yt_track, sp_track)

            if dist < closest_track_dist:
                closest_track = yt_track
                closest_track_dist = dist

        if closest_track_dist > 20:
            return None

        return closest_track

    def _track_dist(self, track1: BaseTrack, track2: BaseTrack) -> int:
        title_dist = Levenshtein.distance(track1.title, track2.title)

        # album distance is ignored
        # the same song can be released as a single or part of an album
        album_dist = 0

        artist_dists = [None] * len(track1.artists)
        for i, artist1 in enumerate(track1.artists):
            curr_artist_lowest_dist = 999
            for artist2 in track2.artists:
                dist = Levenshtein.distance(artist1, artist2, weights=(1, 1, 1))
                if dist < curr_artist_lowest_dist:
                    curr_artist_lowest_dist = dist
            artist_dists[i] = curr_artist_lowest_dist

        # number of artists varies by more than one
        if abs(len(track1.artists) - len(track2.artists)) > 1:
            return 999

        # number of artists varies by one
        if len(track1.artists) != len(track2.artists) and len(artist_dists) > 1:
            artist_dists.sort()
            artist_dists.pop(-1)

        return title_dist * 1 \
               + sum(artist_dists) * 2 \
               + album_dist * 1
