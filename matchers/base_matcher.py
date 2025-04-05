"""Base matcher interface for music matching."""

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List


class BaseMatcher(ABC):
    """Base abstract class for music track matchers."""

    def __init__(self, logger: logging.Logger):
        """Initialize base matcher.

        Args:
            logger: Logger instance
        """
        self.logger = logger

    @abstractmethod
    def score_candidates(
        self, spotify_track: Dict[str, Any], youtube_results: List[Dict[str, Any]]
    ) -> List[tuple]:
        """Score YouTube candidates against a Spotify track.

        Args:
            spotify_track: Spotify track data
            youtube_results: List of YouTube track candidates

        Returns:
            List of (score, track) tuples sorted by descending score
        """
        pass

    @abstractmethod
    def select_best_match(
        self, spotify_track: Dict[str, Any], scored_results: List[tuple]
    ) -> Dict[str, Any]:
        """Select the best match from scored results.

        Args:
            spotify_track: Spotify track data
            scored_results: List of (score, track) tuples

        Returns:
            Best matching YouTube track
        """
        pass
