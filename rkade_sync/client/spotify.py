# client/spotify.py
import json
import os
import typing as T

from spotipy import Spotify
from spotipy.oauth2 import SpotifyClientCredentials


class SpotifyClient(Spotify):
    def __init__(self, client_id, client_secret, user):
        super().__init__(
            auth_manager=SpotifyClientCredentials(
                client_id=client_id, client_secret=client_secret
            )
        )
        self.user = user

    def get_spotify_playlists_and_songs(self, fuzzy_name) -> T.Dict[str, T.List[T.Any]]:
        playlists = self.user_playlists(self.user)
        matched_playlists = {
            pl["name"]: pl["id"]
            for pl in playlists["items"]  # type: ignore
            if fuzzy_name in pl["name"]
        }
        songs = {
            name: [] for name in matched_playlists.keys()
        }  # Pre-populate songs dictionary

        for name, pl_id in matched_playlists.items():
            print(f"getting spotify songs for {name}")
            all_playlist_items = self.get_all_playlist_items(
                pl_id
            )  # Helper function for clarity
            songs[name] = [
                (track["track"]["name"], track["track"]["artists"][0]["name"])
                for track in all_playlist_items
            ]
        return songs

    def get_all_playlist_items(self, pl_id) -> T.List[T.Dict[str, T.Any]]:
        offset = 0
        all_items = []
        while True:
            playlist_items = self.playlist_items(  # type:ignore
                pl_id,
                fields="items(track(name,artists(name)))",
                limit=100,
                offset=offset,
            )["items"]
            all_items.extend(playlist_items)
            if len(playlist_items) < 100:
                break
            offset += 100
        return all_items

    def save_spotify_playlist_song_metadata(
        self, root: str, new_metadata: T.Dict[str, T.List[T.Any]]
    ) -> str:
        dir = f"{root}/metadata"
        os.makedirs(dir, exist_ok=True)

        # Check for metadata if it exists and print summary
        path = f"{dir}/spotify_playlist_song_info.json"
        existing_metadata = {}
        if os.path.isfile(path) and os.access(path, os.R_OK):
            with open(path, "r") as fp:
                existing_metadata = json.load(fp)

        existing_summary = (
            "No existing spotify metadata, creating new file"
            if len(existing_metadata) < 1
            else f"Old: {self._get_summary_metadata(existing_metadata)}"
        )
        print(existing_summary)

        # Handle new summary of metadata
        with open(path, "w") as fp:
            json.dump(new_metadata, fp)
        new_summary = f"New: {self._get_summary_metadata(new_metadata)}"
        print(new_summary)
        return f"Metadata saved at {path}"

    def _get_summary_metadata(
        self, playlist_song_info: T.Dict[str, T.List[T.Any]]
    ) -> str:
        num_playlists = len(playlist_song_info.keys())
        num_songs = sum([len(songs) for songs in playlist_song_info.values()])
        return f"{num_playlists} playlists and {num_songs} songs"
