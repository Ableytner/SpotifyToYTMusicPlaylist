import os
from configparser import ConfigParser

from spotify_helper import SpotifyHelper, SpotifyTrack
from ytmusic_helper import YTMusicHelper

CONFIG_PATH = "config.ini"

def read_config() -> ConfigParser:
    if not os.path.isfile(CONFIG_PATH):
        raise FileNotFoundError()

    parser = ConfigParser()
    parser.read(CONFIG_PATH)
    return parser

def parse_playlists(config: ConfigParser) -> list[dict]:
    playlist_sections = []
    for section in config.sections():
        if section.startswith("playlist") and section != "playlist":
            playlist_sections.append(section)

    playlists = [config[item] for item in playlist_sections]

    # sanitize spotify urls
    for i in range(len(playlists)):
        url = playlists[i]["spotify_url"]
        url = url.replace("https://open.spotify.com/playlist/", "")
        if "?" in url:
            url = url.split("?", maxsplit=1)[0]
        playlists[i]["spotify_url"] = url
    
    return playlists

if __name__ == "__main__":
    config = read_config()

    playlists = parse_playlists(config)
    if len(playlists) == 0:
        raise Exception("No playlist found in config.ini")

    spotifyHelper = SpotifyHelper(config["spotify"])
    spotifyHelper.authorize()

    ytmusic_helper = YTMusicHelper()
    ytmusic_helper.authorize()
    
    playlist_data: dict[str, list[SpotifyTrack]] = {}
    for playlist in playlists:
        (name, tracks) = spotifyHelper.get_playlist(playlist["spotify_url"])
        if name in playlist_data.keys():
            raise Exception("Two spotify playlists with the same name detected")
        playlist_data[name] = tracks

    for name, tracks in playlist_data.items():    
        ytmusic_helper.add_playlist(name, tracks)
