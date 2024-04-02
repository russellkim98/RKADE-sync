import multiprocessing
import subprocess
import typing as T

from client.spotify import SpotipyClient
from client.yt_music import YTMusicClient
from config import (
    ROOT_DIR,
    SPOTIPY_CLIENT_ID,
    SPOTIPY_CLIENT_SECRET,
    SPOTIPY_USER,
    YT_PLAYLISTS,
)
from helpers import media, utils

RAW_DIR = f"{ROOT_DIR}/raw"


def initialize_clients() -> tuple[SpotipyClient, YTMusicClient]:
    """Initializes Spotify and Youtube Music clients.

    Returns:
        A tuple containing the initialized SpotipyClient and YTMusicClient instances.
    """

    return (
        SpotipyClient(
            client_id=SPOTIPY_CLIENT_ID,
            client_secret=SPOTIPY_CLIENT_SECRET,
            user=SPOTIPY_USER,
        ),
        YTMusicClient(auth="oauth.json"),
    )


def download_song(yt_video: media.YTVideo, playlist):
    final_directory = f"{ROOT_DIR}/playlists/{playlist}"
    file_path = yt_video.download_mp3(
        raw_directory=RAW_DIR, final_directory=final_directory
    )
    utils.set_thumbnail(file_path, yt_video.youtube.thumbnail_url)


def main():
    """The main entry point for the script."""

    subprocess.run(["ytmusicapi", "oauth"])
    sp_client, ytm_client = initialize_clients()
    sp_playlists = sp_client.get_spotify_playlists_and_songs(fuzzy_name="rekordbox")
    sp_videos = media.get_spotify_videos(sp_playlists, ytm_client)
    yt_videos = media.get_ytm_videos(YT_PLAYLISTS)
    return sp_videos | yt_videos


if __name__ == "__main__":
    tracks = main()
    manager = multiprocessing.Manager()
    processes = []
    for playlist, videos in tracks.items():
        for video in videos:
            p = multiprocessing.Process(
                target=download_song,
                args=(
                    video,
                    playlist,
                ),
            )
            processes.append(p)
            p.start()

    for process in processes:
        process.join()
