import spotipy
import typing as T
import logging


class SpotipyClient(spotipy.Spotify):
    """
    Spotipy client for use in getting playlist information
    """

    def __init__(self, client_id: str, client_secret: str, **kwargs):
        super().__init__(
            auth_manager=spotipy.oauth2.SpotifyClientCredentials(
                client_id=client_id, client_secret=client_secret
            )
        )
        if "user" not in kwargs:
            raise ValueError("user must be provided")
        self.user = kwargs.get("user", "")
        self._user_playlists = self.user_playlists(user=self.user)

    def get_spotify_playlists_and_songs(
        self, fuzzy_name: str
    ) -> T.Dict[str, T.Dict[str, T.Any]]:
        """
        Get the Spotify playlists and populate with songs
        """
        playlist_ids = self._get_playlists(fuzzy_name)
        playlist_and_songs = {
            id: {"id": id, "name": name, "songs": self._get_songs_in_playlist(id, name)}
            for id, name in playlist_ids
        }

        return playlist_and_songs

    def _get_playlists(self, fuzzy_name: str) -> T.List[T.Tuple[str, str]]:
        # Filter to playlists with desired names
        if self._user_playlists is None:
            return []
        filtered_playlists = [
            (pl["id"], pl["name"])
            for pl in self._user_playlists["items"]
            if fuzzy_name in pl["name"]
        ]
        return filtered_playlists

    def _get_songs_in_playlist(self, id: str, name: str) -> T.List[T.Tuple[str, str]]:
        """
        Get the songs in a playlist
        """
        songs = []
        offset = 0
        limit = 50
        logging.log(level=logging.INFO, msg=f"Getting songs for {name} : {id}")
        print(f"Getting songs for {name} : {id}")
        while offset % limit == 0:
            # This is a limit of 50
            offset_songs = self.playlist_items(
                id,
                fields="items(track(artists(name), id, name))",
                limit=limit,
                offset=offset,
            )
            if offset_songs is None:
                continue

            new_songs = offset_songs["items"]
            for song in new_songs:
                full_name, artist_names = self._extract_metadata(song)
                songs.append((full_name, artist_names))
            offset += len(new_songs)

            print(f"Songs loaded: {len(songs)}")
        return [s for s in songs]

    def _extract_metadata(self, song: T.Dict[str, T.Any]) -> T.Tuple[str, str]:
        """
        Return song names and artist names of the provided song dict
        """
        artist_names = " & ".join([a["name"] for a in song["track"]["artists"]])
        song_name = song["track"]["name"]
        full_name = f"""{artist_names} - {song_name}"""
        return full_name, artist_names
