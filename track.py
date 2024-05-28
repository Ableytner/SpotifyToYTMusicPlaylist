from __future__ import annotations
from abc import ABC
from dataclasses import dataclass
import os.path
import re

from ytmusicapi import YTMusic

@dataclass
class BaseTrack(ABC):
    title: str
    artists: list[str]
    album: str

    def __post_init__(self):
        if "(feat" in self.title:
            extra_artists = re.search(r" \(feat.*\)", self.title)
            if extra_artists is not None:
                extra_artists = extra_artists.group().strip(" ()").replace("feat. ", "")
                self._split_and_add_extra_artists(extra_artists)

            self.title = re.sub(r"\(feat.*\)", "", self.title).strip()

        if "[feat" in self.title:
            extra_artists = re.search(r" \[feat.*\]", self.title)
            if extra_artists is not None:
                extra_artists = extra_artists.group().strip(" []").replace("feat. ", "")
                self._split_and_add_extra_artists(extra_artists)

            self.title = re.sub(r"\[feat.*\]", "", self.title).strip()

        if re.search(r" \- .* Remix", self.title) is not None:
            extra_artists = re.search(r" \- .* Remix", self.title)
            if extra_artists is not None:
                extra_artists = extra_artists.group().strip(" -").replace(" Remix", "")
                self._split_and_add_extra_artists(extra_artists)

        if re.search(r" \(.* Remix\)", self.title) is not None:
            extra_artists = re.search(r" \(.* Remix\)", self.title)
            if extra_artists is not None:
                extra_artists = extra_artists.group().strip(" ()").replace(" Remix", "")
                self._split_and_add_extra_artists(extra_artists)

        if re.search(r" \[.* Remix\]", self.title) is not None:
            extra_artists = re.search(r" \[.* Remix\]", self.title)
            if extra_artists is not None:
                extra_artists = extra_artists.group().strip(" []").replace(" Remix", "")
                self._split_and_add_extra_artists(extra_artists)

        if self.title == "":
            raise ValueError(f"title cannot be empty in {self}")
        if self.album == "":
            raise ValueError(f"album cannot be empty in {self}")
        if len(self.artists) == 0:
            raise ValueError(f"artists cannot be empty in {self}")

    def _split_and_add_extra_artists(self, extra_artists: str) -> None:
        extra_artists = extra_artists.strip().split(", ")

        for i in range(len(extra_artists)):
            if " & " in extra_artists[i]:
                tmp = extra_artists[i].split(" & ")
                extra_artists[i] = tmp.pop(0)
                extra_artists += tmp
        for i in range(len(extra_artists)):
            if " x " in extra_artists[i]:
                tmp = extra_artists[i].split(" x ")
                extra_artists[i] = tmp.pop(0)
                extra_artists += tmp
        
        for artist in extra_artists:
            if artist not in self.artists:
                self.artists.append(artist)

@dataclass
class SpotifyTrack(BaseTrack):
    @staticmethod
    def from_response(response) -> SpotifyTrack | None:
        return SpotifyTrack(title=response["name"],
                            artists=[item["name"] for item in response['artists']],
                            album=response["album"]["name"])

@dataclass
class YtMusicTrack(BaseTrack):
    video_id: str

    @staticmethod
    def from_response(response) -> YtMusicTrack | None:
        if response is None or "album" not in response.keys() or response["album"] is None or "name" not in response["album"]:
            return None

        artists = [item["name"] for item in response["artists"]]
        # sometimes YouTube messes up and doesn't return artists for a song
        # in this case, the album contains only one artist which is the actual artists but comma seperated
        # likely to break in the future
        if len(artists) == 0:
            if os.path.isfile("oauth.json"):
                album_res = YTMusic("oauth.json").get_album(response["album"]["id"])
                artists = album_res["artists"][0]["name"].split(", ")

        return YtMusicTrack(title=response["title"],
                            artists=artists,
                            album=response["album"]["name"],
                            video_id=response["videoId"])
