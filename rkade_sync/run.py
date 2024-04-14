import json
import os

from client.spotify import SpotifyClient
from client.youtube_music import YouTubeMusicClient
from config import (
    ROOT_DIR,
    SPOTIFY_CLIENT_ID,
    SPOTIFY_CLIENT_SECRET,
    SPOTIFY_USER,
    YOUTUBE_MUSIC_HEADERS,
    YT_PLAYLISTS,
)
from helpers import media_helpers, utils

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
    youtube_music_client = YouTubeMusicClient(auth=YOUTUBE_MUSIC_HEADERS)
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


def main():
    """Downloads songs from Spotify and Youtube Music playlists.

    Performs user authentication for Youtube Music and initializes clients for both services.
    Then retrieves video information from playlists and returns a dictionary containing
    all videos categorized by playlist.

    Returns:
        A dictionary where keys are playlist names and values are lists of video objects.
        (The specific video object type depends on the used libraries)
    """
    spotify_client, youtube_music_client = initialize_clients()
    # get spotify playlists
    # spotify_metadata = spotify_client.get_spotify_playlists_and_songs("rekordbox")
    with open(f"{ROOT_DIR}/metadata/spotify_playlist_song_info.json", "r") as fp:
        spotify_metadata = json.load(fp)

    # save spotify playlist information to json
    result = spotify_client.save_spotify_playlist_song_metadata(
        root=ROOT_DIR, new_metadata=spotify_metadata
    )


if __name__ == "__main__":
    main()
