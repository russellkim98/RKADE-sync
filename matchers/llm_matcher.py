"""LLM-based matcher for music tracks."""

import logging
from typing import Any, Dict, List

from clients.llm_client import LLMClient
from matchers.base_matcher import BaseMatcher


class LLMMatcher(BaseMatcher):
    """Matcher that uses LLM to find best track match."""

    def __init__(self, llm_client: LLMClient, logger: logging.Logger):
        """Initialize LLM matcher.

        Args:
            llm_client: LLM client for queries
            logger: Logger instance
        """
        super().__init__(logger)
        self.llm_client = llm_client

    def score_candidates(
        self, spotify_track: Dict[str, Any], youtube_results: List[Dict[str, Any]]
    ) -> List[tuple]:
        """Score isn't very meaningful for LLM matcher.

        Args:
            spotify_track: Spotify track data
            youtube_results: List of YouTube track candidates

        Returns:
            List of (score, track) tuples (placeholder scores)
        """
        # LLM matcher doesn't do traditional scoring, it just returns the candidates
        # with placeholder scores for API compatibility
        scored_results = [(100.0 - i, track) for i, track in enumerate(youtube_results)]
        return scored_results

    def select_best_match(
        self, spotify_track: Dict[str, Any], scored_results: List[tuple] = None
    ) -> Dict[str, Any]:
        """Select best match using LLM judgment.

        Args:
            spotify_track: Spotify track data
            scored_results: Either list of (score, track) tuples or list of tracks

        Returns:
            Best matching YouTube track
        """
        # Handle either scored results or direct candidates
        candidates = []
        if scored_results:
            if isinstance(scored_results[0], tuple):
                candidates = [result[1] for result in scored_results[:3]]
            else:
                candidates = scored_results[:3]

        if not candidates:
            self.logger.warning("No candidates provided to LLM matcher")
            return {}

        # Use LLM to select best match
        self.logger.debug("Using LLM to judge best match")
        return self.llm_client.judge_candidates(spotify_track, candidates)
