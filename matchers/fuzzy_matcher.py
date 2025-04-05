"""Fuzzy matching implementation for music tracks."""

import logging
from typing import Any, Dict, List, Tuple

from fuzzywuzzy import fuzz
from Levenshtein import jaro_winkler

from matchers.base_matcher import BaseMatcher
from utils.text_processing import preprocess_text


class FuzzyMatcher(BaseMatcher):
    """Matcher that uses fuzzy string matching to find best track match."""

    def __init__(
        self,
        title_weight: float,
        artist_weight: float,
        duration_weight: float,
        llm_score_threshold: float,
        llm_score_difference: float,
        logger: logging.Logger,
        llm_matcher=None,  # Will be set after initialization to avoid circular import
    ):
        """Initialize fuzzy matcher.

        Args:
            title_weight: Weight for title match score
            artist_weight: Weight for artist match score
            duration_weight: Weight for duration match score
            llm_score_threshold: Threshold below which to use LLM
            llm_score_difference: Score difference below which to use LLM
            logger: Logger instance
            llm_matcher: Optional LLM matcher for fallback
        """
        super().__init__(logger)
        self.title_weight = title_weight
        self.artist_weight = artist_weight
        self.duration_weight = duration_weight
        self.llm_score_threshold = llm_score_threshold
        self.llm_score_difference = llm_score_difference
        self.llm_matcher = llm_matcher

    def set_llm_matcher(self, llm_matcher):
        """Set LLM matcher for fallback.

        Args:
            llm_matcher: LLM matcher instance
        """
        self.llm_matcher = llm_matcher

    def score_candidates(
        self, spotify_track: Dict[str, Any], youtube_results: List[Dict[str, Any]]
    ) -> List[Tuple[float, Dict[str, Any]]]:
        """Score YouTube candidates against a Spotify track using fuzzy matching.

        Args:
            spotify_track: Spotify track data
            youtube_results: List of YouTube track candidates

        Returns:
            List of (score, track) tuples sorted by descending score
        """
        sp_title = preprocess_text(spotify_track["name"])
        sp_artist = preprocess_text(spotify_track["artists"][0]["name"])
        sp_duration = spotify_track["duration_ms"] // 1000

        self.logger.debug(
            f"MATCHING TRACK: {spotify_track['name']} by {spotify_track['artists'][0]['name']}\n"
            f"Duration: {sp_duration}s | Album: {spotify_track['album']['name']}"
        )

        # Score all candidates using fuzzy matching
        scored_results = []
        for yt_track in youtube_results:
            yt_title = preprocess_text(yt_track.get("title", ""))
            yt_artist = (
                preprocess_text(yt_track["artists"][0]["name"])
                if yt_track.get("artists")
                else ""
            )
            yt_duration = yt_track.get("duration_seconds", 0)

            title_score = fuzz.token_sort_ratio(sp_title, yt_title)
            artist_score = jaro_winkler(sp_artist, yt_artist) * 100
            duration_score = max(0, 100 - abs(sp_duration - yt_duration))

            total_score = (
                title_score * self.title_weight
                + artist_score * self.artist_weight
                + duration_score * self.duration_weight
            )

            scored_results.append((total_score, yt_track))

            self.logger.debug(
                f"Candidate: {yt_track.get('title', '')}\n"
                f"  Artist: {yt_track['artists'][0]['name'] if yt_track.get('artists') else 'Unknown'}\n"
                f"  Duration: {yt_duration}s\n"
                f"  Scores:\n"
                f"    Title: {title_score:.1f}\n"
                f"    Artist: {artist_score:.1f}\n"
                f"    Duration: {duration_score:.1f}\n"
                f"    TOTAL: {total_score:.1f}"
            )

        # Sort by descending score
        scored_results.sort(reverse=True, key=lambda x: x[0])

        self.logger.debug("TOP CANDIDATES:")
        for i, (score, candidate) in enumerate(scored_results[:3], 1):
            self.logger.debug(f"{i}. {candidate.get('title', '')} - Score: {score:.1f}")

        return scored_results

    def select_best_match(
        self,
        spotify_track: Dict[str, Any],
        scored_results: List[Tuple[float, Dict[str, Any]]],
    ) -> Dict[str, Any]:
        """Select best match, falling back to LLM if scores are ambiguous.

        Args:
            spotify_track: Spotify track data
            scored_results: List of (score, track) tuples sorted by descending score

        Returns:
            Best matching YouTube track
        """
        if not scored_results:
            self.logger.warning("No candidates to select from")
            return {}

        # Check if we should use LLM fallback
        if (
            len(scored_results) > 0 and scored_results[0][0] < self.llm_score_threshold
        ) or (
            len(scored_results) > 1
            and (scored_results[0][0] - scored_results[1][0])
            < self.llm_score_difference
        ):
            if self.llm_matcher:
                self.logger.info(
                    "Using LLM for final judgment (close scores or low confidence)"
                )
                top_candidates = [result[1] for result in scored_results[:3]]
                return self.llm_matcher.select_best_match(spotify_track, top_candidates)
            else:
                self.logger.warning(
                    "LLM matcher not available for fallback, using top candidate"
                )

        self.logger.info(f"Clear winner selected with score {scored_results[0][0]:.1f}")
        return scored_results[0][1]
