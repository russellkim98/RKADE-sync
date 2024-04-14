from typing import Any, Dict, List

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

    def get_spotify_playlists_and_songs(self, fuzzy_name) -> Dict[str, List[Any]]:
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
                {
                    "title": track["track"]["name"],
                    "artist": track["track"]["artists"][0]["name"],
                    "album": track["track"]["album"]["name"],
                    "duration_ms": track["track"]["duration_ms"],
                }
                for track in all_playlist_items
            ]

        return songs

    def get_all_playlist_items(self, pl_id) -> List[Dict[str, Any]]:
        offset = 0
        all_items = []
        while True:
            playlist_items = self.playlist_items(  # type:ignore
                pl_id,
                fields="items(track(name,artists(name), album(name),duration_ms))",
                limit=100,
                offset=offset,
            )["items"]
            all_items.extend(playlist_items)
            if len(playlist_items) < 100:
                break
            offset += 100
        return all_items
