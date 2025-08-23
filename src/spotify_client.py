"""Client for interacting with the Spotify API."""

import json
import logging
import os
from pathlib import Path
from typing import List, Dict, Any

import spotipy
from spotipy.oauth2 import SpotifyOAuth

from .config import (
    SPOTIFY_CLIENT_ID,
    SPOTIFY_CLIENT_SECRET,
    SPOTIFY_REDIRECT_URI,
)
from .data_models import Track

logger = logging.getLogger(__name__)

CACHE_PATH = Path("spotify_cache.json")


class SpotifyManager:
    def __init__(self):
        self.client = None
        self.cache = self._load_cache()

    def _load_cache(self) -> Dict[str, Any]:
        """Loads the Spotify cache from a JSON file."""
        if CACHE_PATH.exists():
            with open(CACHE_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"tracks": {}}

    def _save_cache(self):
        """Saves the Spotify cache to a JSON file."""
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(self.cache, f, indent=4)

    def authenticate(self):
        """Authenticate with Spotify."""
        try:
            self.client = spotipy.Spotify(
                auth_manager=SpotifyOAuth(
                    client_id=SPOTIFY_CLIENT_ID,
                    client_secret=SPOTIFY_CLIENT_SECRET,
                    redirect_uri=SPOTIFY_REDIRECT_URI,
                    scope="user-library-read playlist-read-private playlist-read-collaborative",
                )
            )
            user = self.client.current_user()
            logger.info(f"✅ Connected to Spotify as: {user['display_name']}")
            return True
        except Exception as e:
            logger.error(f"❌ Spotify authentication failed: {e}")
            return False

    def get_liked_songs(self) -> List[Track]:
        """Get all liked songs from Spotify, using cache if available."""
        logger.info("Fetching liked songs from Spotify...")
        cached_tracks = self.cache["tracks"].get("liked_songs")
        if cached_tracks:
            logger.info("Found liked songs in cache.")
            return [Track(**t) for t in cached_tracks]

        tracks = self._fetch_all_pages(self.client.current_user_saved_tracks)
        self.cache["tracks"]["liked_songs"] = [t.to_dict() for t in tracks]
        self._save_cache()
        logger.info(f"✅ Found {len(tracks)} liked songs on Spotify")
        return tracks

    def get_all_playlists(self) -> List[Track]:
        """Get tracks from all user playlists, using cache if available."""
        logger.info("Fetching all playlists from Spotify...")
        cached_playlists = self.cache["tracks"].get("playlists")
        if cached_playlists:
            logger.info("Found playlists in cache.")
            return [Track(**t) for t in cached_playlists]

        all_tracks = []
        try:
            user_id = self.client.current_user()["id"]
            playlists = self._fetch_all_pages(self.client.current_user_playlists)

            for playlist in playlists:
                if (
                    playlist["owner"]["id"] == user_id
                    and "rekordbox_" in playlist["name"]
                ):
                    tracks = self.get_playlist_tracks(playlist["id"], playlist["name"])
                    all_tracks.extend(tracks)

            self.cache["tracks"]["playlists"] = [t.to_dict() for t in all_tracks]
            self._save_cache()
        except Exception as e:
            logger.error(f"❌ Error fetching playlists: {e}")

        return all_tracks

    def get_playlist_tracks(self, playlist_id: str, playlist_name: str) -> List[Track]:
        """Get tracks from a specific playlist."""
        logger.info(f"Fetching playlist: {playlist_name}")
        results = self.client.playlist_tracks(playlist_id)
        return self._parse_track_results(results, f"spotify_playlist_{playlist_name}")

    def _fetch_all_pages(self, api_call) -> List[Track]:
        """Fetches all pages from a paginated Spotify API endpoint."""
        tracks = []
        results = api_call()
        while results:
            tracks.extend(self._parse_track_results(results, "spotify_liked"))
            if results["next"]:
                results = self.client.next(results)
            else:
                break
        return tracks

    def _parse_track_results(self, results: Dict, source: str) -> List[Track]:
        """Parses track results from the Spotify API."""
        tracks = []
        for item in results["items"]:
            if item.get("track") and item["track"].get("id"):
                track_data = item["track"]
                track = Track(
                    name=track_data["name"],
                    artist=", ".join(
                        [artist["name"] for artist in track_data["artists"]]
                    ),
                    album=track_data["album"]["name"],
                    duration_ms=track_data["duration_ms"],
                    spotify_id=track_data["id"],
                    source=source,
                    popularity=track_data["popularity"],
                    release_date=track_data["album"]["release_date"],
                )
                tracks.append(track)
        return tracks
