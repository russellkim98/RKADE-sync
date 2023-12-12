import subprocess
from pathlib import Path
from client.spotify import SpotipyClient
from client.yt_music import YTMusicClient


from config import (
    SPOTIPY_CLIENT_ID,
    SPOTIPY_CLIENT_SECRET,
    ROOT_DIR,
    YTMUSIC_OAUTH_DIR,
    YT_PLAYLISTS,
    USER,
)
import asyncio
import typing as T


def parse_yt_urls(file_path) -> T.Dict[str, bool]:
    """
    Parses a text file containing YouTube URLs at the given path and creates a dictionary
    of video IDs mapped to True.

    Args:
      file_path: Path to the text file.

    Returns:
      A dictionary mapping video IDs to True.
    """
    video_ids = {}
    with Path(file_path).open() as f:
        for line in f:
            if line.startswith("youtube "):
                video_id = line.split(" ")[1].rstrip("\n")
                video_ids[video_id] = True
    return video_ids


async def download_song(
    client_yt: YTMusicClient,
    song: str,
    artist: str,
    playlist: str,
    playlist_dir: str,
    archive_path: str,
    archive_dict: T.Dict[str, bool],
) -> str:
    print(f"trying to download {song}")
    title, video_id = client_yt.return_top_songs(song)
    if video_id in archive_dict:
        return "Exists."
    else:
        command = client_yt.create_ytdlp_cmd(
            video_id=video_id,
            title=title,
            artist=artist,
            archive_path=archive_path,
            output_dir=playlist_dir,
        )

        r = subprocess.run([command], shell=True)

        # Check if the command was successful
        if r.returncode == 0:
            return f"Downloaded {title} from {playlist}"
        else:
            return f"Failed to download {title} from {playlist}"


async def main():
    # Create clients
    client_sp = SpotipyClient(SPOTIPY_CLIENT_ID, SPOTIPY_CLIENT_SECRET, user=USER)
    client_yt = YTMusicClient(YTMUSIC_OAUTH_DIR)
    # Grab all spotify playlists
    sp_playlists = client_sp.get_spotify_playlists_and_songs(fuzzy_name="rekordbox")
    results = []
    archive_path = f"{ROOT_DIR}/archive.txt"
    archive_dict = parse_yt_urls(archive_path)

    # Create a folder for each playlist if it doesn't exist in library/raw
    for entry in sp_playlists.values():
        playlist_name, playlist_songs = entry["name"], entry["songs"]
        playlist_dir = f"{ROOT_DIR}/raw/{playlist_name}"
        Path(playlist_dir).mkdir(parents=True, exist_ok=True)
        # Search for songs
        playlist_results = await asyncio.gather(
            *[
                download_song(
                    client_yt,
                    song,
                    artist,
                    playlist_name,
                    playlist_dir,
                    archive_path,
                    archive_dict,
                )
                for song, artist in playlist_songs
            ]
        )
        results.append(playlist_results)
    return results


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main())
