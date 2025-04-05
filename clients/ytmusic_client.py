"""YouTube Music API client for music matching."""

import logging
from typing import Dict, List

from ytmusicapi import YTMusic


class YTMusicClient:
    """Client for interacting with YouTube Music API."""

    def __init__(self, auth_path: str, logger: logging.Logger):
        """Initialize YouTube Music client.

        Args:
            auth_path: Path to auth JSON file for YTMusic
            logger: Logger instance

        Raises:
            Exception: If initialization fails
        """
        self.logger = logger
        try:
            self.client = YTMusic(auth=auth_path)
            self.logger.info("YouTube Music client initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize YouTube Music client: {str(e)}")
            raise

    def search_tracks(self, query: str, max_results: int = 10) -> List[Dict]:
        """Search for tracks on YouTube Music.

        Args:
            query: Search query
            max_results: Maximum number of results to return

        Returns:
            List of track results

        Raises:
            Exception: If search fails
        """
        try:
            self.logger.debug(f"Searching YouTube Music for: {query}")
            results = self.client.search(query, filter="songs", limit=max_results)
            self.logger.debug(f"Found {len(results)} results")
            return results
        except Exception as e:
            self.logger.error(f"YouTube Music search failed: {str(e)}")
            raise

    def get_track_details(self, video_id: str) -> Dict:
        """Get detailed information about a track.

        Args:
            video_id: YouTube video ID

        Returns:
            Track details

        Raises:
            Exception: If fetching details fails
        """
        try:
            self.logger.debug(f"Fetching details for YouTube track {video_id}")
            return self.client.get_song(video_id)
        except Exception as e:
            self.logger.error(f"Failed to get YouTube track details: {str(e)}")
            raise
