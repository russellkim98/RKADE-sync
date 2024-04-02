import multiprocessing as mp
import os
import subprocess
from pathlib import Path

from client.spotify import SpotifyClient
from client.youtube_music import YouTubeMusicClient
from config import (
    ROOT_DIR,
    SPOTIFY_CLIENT_ID,
    SPOTIFY_CLIENT_SECRET,
    SPOTIFY_USER,
    YT_PLAYLISTS,
)
from helpers import media_helpers, utils
from tqdm import tqdm

RAW_DIR = f"{ROOT_DIR}/raw"


def initialize_clients() -> tuple[SpotifyClient, YouTubeMusicClient]:
    """Initializes Spotify and Youtube Music clients.

    Returns:
        A tuple containing the SpotifyClient and YouTubeMusicClient instances.
    """

    spotify_client = SpotifyClient(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET,
        user=SPOTIFY_USER,
    )
    youtube_music_client = YouTubeMusicClient(auth="oauth.json")
    return spotify_client, youtube_music_client


def download_song(yt_video: media_helpers.YouTubeVideo, playlist: str) -> None:
    """Downloads a YouTube Music video as MP3 and sets its thumbnail.

    Args:
        yt_video: The YouTube Music video object. (Expected type depends on the specific library)
        playlist: The name of the playlist the video belongs to.
    """

    print(f"downloading {yt_video.track}")
    final_directory = f"{ROOT_DIR}/playlists/{playlist}"
    file_path = yt_video.download_mp3(
        raw_directory=RAW_DIR, final_directory=final_directory
    )
    success = utils.set_thumbnail(file_path, yt_video.thumbnail_url)


def main() -> dict[str, list[object]]:
    """Downloads songs from Spotify and Youtube Music playlists.

    Performs user authentication for Youtube Music and initializes clients for both services.
    Then retrieves video information from playlists and returns a dictionary containing
    all videos categorized by playlist.

    Returns:
        A dictionary where keys are playlist names and values are lists of video objects.
        (The specific video object type depends on the used libraries)
    """

    subprocess.run(["ytmusicapi", "oauth"])
    spotify_client, youtube_music_client = initialize_clients()
    spotify_videos = media_helpers.get_spotify_videos(
        spotify_client.get_spotify_playlists_and_songs("rekordbox"),
        youtube_music_client,
    )
    youtube_videos = media_helpers.get_youtube_music_videos(YT_PLAYLISTS)
    youtube_videos = {}
    return {**spotify_videos, **youtube_videos}


if __name__ == "__main__":
    tracks = main()
    total_songs = sum(
        len(videos) for playlist, videos in tracks.items()
    )  # Count total songs
    progress_counter = mp.Value("i", 0)  # Shared counter for progress
    pool = mp.Pool(3)

    with tqdm(total=total_songs, desc="Downloading Songs") as pbar:
        for playlist, videos in tracks.items():
            os.makedirs(f"{ROOT_DIR}/playlists/{playlist}", exist_ok=True)
            for video in videos:
                pool.starmap_async(
                    download_song,
                    [(video, playlist)],
                    callback=lambda _: progress_counter.value + 1,
                )
                utils.set_thumbnail(
                    f"{ROOT_DIR}/playlists/{playlist}/{video.track}.mp3",  # type: ignore
                    video.thumbnail_url,  # type: ignore
                )

    pool.close()
    pool.join()

    # Ensure final update after all downloads are complete
    pbar.update(progress_counter.value)
