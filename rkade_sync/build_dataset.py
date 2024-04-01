import subprocess
from pathlib import Path
from client.spotify import SpotipyClient
from client.yt_music import YTMusicClient
import logging
import sys
import json


from config import (
    SPOTIPY_CLIENT_ID,
    SPOTIPY_CLIENT_SECRET,
    ROOT_DIR,
    YTMUSIC_OAUTH_DIR,
    YT_PLAYLISTS,
    USER,
)
import typing as T


def main():
    client_sp = SpotipyClient(SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET, user=USER)
    with open("songs.json") as f:
        songs = json.load(f)
    for pl_id, pl_info in songs.items():
        num_tracks = pl_info["num_tracks"]
        q = num_tracks // 100


if __name__ == "__main__":
    main()
