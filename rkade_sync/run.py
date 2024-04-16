import itertools
import json
import os
from typing import Any, Dict

from config import ROOT, SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_USER
from playlist_manager import PlaylistManager
from spotify import SpotifyClient

# Set debug flags
INFO_DEBUG = False
DOWNLOAD_DEBUG = False


def get_metadata_from_file(path: str) -> Dict[str, Any]:
    """
    Retrieve metadata from a JSON file.

    Args:
        path (str): Path to the JSON file.

    Returns:
        Dict[str, Any]: Metadata stored in the file.
    """
    if os.path.exists(path) and os.path.getsize(path) > 0:
        with open(path, "r") as file:
            data = json.load(file)
    else:
        data = {}
    return data


def write_metadata_to_file(data: Dict[str, Any], path: str) -> None:
    """
    Write metadata to a JSON file.

    Args:
        data (Dict[str, Any]): Metadata to be written.
        path (str): Path to the JSON file.
    """
    with open(path, "w") as file:
        json.dump(data, file, indent=4)


def main():
    """
    Main function to execute the program.
    """
    # Initialize necessary objects
    playlist_manager = PlaylistManager(ROOT)
    spotify_client = SpotifyClient(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET,
        user=SPOTIFY_USER,
    )

    # Set up metadata paths
    metadata_path = f"{ROOT}/metadata"
    os.makedirs(metadata_path, exist_ok=True)
    youtube_path = f"{metadata_path}/youtube_playlists.json"
    spotify_path = f"{metadata_path}/spotify_playlists.json"
    playlists_path = f"{metadata_path}/playlists.json"

    # Fetch or generate metadata based on debug flags
    if INFO_DEBUG:
        youtube_info = get_metadata_from_file(youtube_path)
        spotify_info = get_metadata_from_file(spotify_path)
    else:
        youtube_info = playlist_manager.ytm_downloader.get_youtube_playlists()
        spotify_info = spotify_client.get_spotify_playlists_and_songs()

    # Write metadata to files
    write_metadata_to_file(youtube_info, youtube_path)
    write_metadata_to_file(spotify_info, spotify_path)

    # Fetch playlist data based on debug flags
    if DOWNLOAD_DEBUG:
        playlist_info = get_metadata_from_file(playlists_path)
    else:
        playlist_info = {}
        for name in set(itertools.chain(youtube_info.keys(), spotify_info.keys())):
            songs = list(
                itertools.chain(spotify_info.get(name, {}), youtube_info.get(name, {}))
            )
            info = playlist_manager.standardize_playlist(name, songs)
            playlist_info[name] = info

    write_metadata_to_file(playlist_info, playlists_path)
    # Download playlists and update metadata
    print("downloading playlists..")
    for name, info in playlist_info.items():
        playlist_info[name] = playlist_manager.download_playlist(name, info)
        print(name)
    write_metadata_to_file(playlist_info, playlists_path)

    print("Done!")


if __name__ == "__main__":
    main()
