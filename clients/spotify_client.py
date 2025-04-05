"""Spotify API client for music matching."""

import logging
from typing import Dict, List, Optional

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials


class SpotifyClient:
    """Client for interacting with Spotify API."""

    def __init__(self, client_id: str, client_secret: str, logger: logging.Logger):
        """Initialize Spotify client.

        Args:
            client_id: Spotify API client ID
            client_secret: Spotify API client secret
            logger: Logger instance
        """
        self.logger = logger
        self.client = self._init_spotify_client(client_id, client_secret)

    def _init_spotify_client(
        self, client_id: str, client_secret: str
    ) -> spotipy.Spotify:
        """Initialize and return authenticated Spotify client.

        Args:
            client_id: Spotify API client ID
            client_secret: Spotify API client secret

        Returns:
            Authenticated Spotify client instance

        Raises:
            Exception: If authentication fails
        """
        try:
            auth_manager = SpotifyClientCredentials(
                client_id=client_id, client_secret=client_secret
            )
            return spotipy.Spotify(auth_manager=auth_manager)
        except Exception as e:
            self.logger.error(f"Failed to initialize Spotify client: {str(e)}")
            raise

    def get_track(self, track_id: str) -> Dict:
        """Get track details by ID.

        Args:
            track_id: Spotify track ID

        Returns:
            Track details

        Raises:
            Exception: If API request fails
        """
        try:
            self.logger.debug(f"Fetching Spotify track {track_id}")
            results = self.get_track(track_id)
            if isinstance(results, dict):
                return results
            else:
                raise Exception
        except Exception as e:
            self.logger.error(f"Failed to fetch Spotify track {track_id}: {str(e)}")
            raise

    def get_playlist_tracks(
        self, playlist_id: str, market: Optional[str] = None, batch_size: int = 100
    ) -> List[str]:
        """Retrieve all track IDs from a Spotify playlist with pagination.

        Args:
            playlist_id: Spotify playlist ID
            market: Optional market code for content filtering
            batch_size: Number of tracks to fetch per request

        Returns:
            List of track IDs in the playlist

        Raises:
            Exception: If API request fails
        """
        self.logger.info(f"Fetching tracks from playlist {playlist_id}")
        track_ids = []
        offset = 0

        try:
            while True:
                self.logger.debug(f"Fetching playlist items batch (offset={offset})")
                results = self.client.playlist_items(
                    playlist_id,
                    fields="items(track(id))",
                    limit=batch_size,
                    offset=offset,
                    market=market,
                    additional_types=["track"],
                )
                if not isinstance(results, dict):
                    raise Exception("Results of playlist tracks is none.")

                items = results.get("items", [])
                if not items:
                    break

                batch_ids = [
                    item["track"]["id"]
                    for item in items
                    if item.get("track", {}).get("id")
                ]
                track_ids.extend(batch_ids)

                self.logger.debug(f"Found {len(batch_ids)} tracks in batch")

                if len(items) < batch_size:
                    break

                offset += batch_size

            self.logger.info(f"Retrieved {len(track_ids)} track IDs from playlist")
            return track_ids

        except Exception as e:
            self.logger.error(f"Failed to fetch playlist tracks: {str(e)}")
            raise

    def get_rekordbox_playlists(self, user_id: str) -> Dict[str, str]:
        """Get rekordbox playlists from Spotify user.

        Args:
            user_id: Spotify user ID

        Returns:
            Dictionary mapping playlist names to playlist IDs

        Raises:
            Exception: If API request fails
        """
        try:
            self.logger.info(f"Fetching rekordbox playlists for user {user_id}")
            playlists = self.client.user_playlists(user_id)
            if not isinstance(playlists, dict):
                raise Exception("Playlists are none.")

            rekordbox_playlists = {
                item["name"]: item["id"]
                for item in playlists["items"]
                if "rekordbox_" in item["name"]
            }

            self.logger.info(f"Found {len(rekordbox_playlists)} rekordbox playlists")
            return rekordbox_playlists

        except Exception as e:
            self.logger.error(f"Failed to fetch rekordbox playlists: {str(e)}")
            raise
