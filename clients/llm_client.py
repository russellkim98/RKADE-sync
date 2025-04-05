"""LLM client for music matching using Ollama."""

import json
import logging
import time
from typing import Any, Dict, Optional, Tuple

import ollama

from database import Database


class LLMClient:
    """Client for interacting with Ollama LLM."""

    def __init__(
        self,
        model: str,
        temperature: float,
        context_size: int,
        logger: logging.Logger,
        db: Optional[Database] = None,
        run_id: Optional[int] = None,
    ):
        """Initialize LLM client.

        Args:
            model: Ollama model name
            temperature: Temperature for generation
            context_size: Context size for generation
            logger: Logger instance
            db: Optional database for tracking
            run_id: Optional run ID for database tracking
        """
        self.model = model
        self.temperature = temperature
        self.context_size = context_size
        self.logger = logger
        self.db = db
        self.run_id = run_id

    def generate_query(
        self, spotify_track: Dict[str, Any], track_match_id: Optional[int] = None
    ) -> str:
        """Generate optimized YouTube search query using LLM with fallback.

        Args:
            spotify_track: Spotify track data
            track_match_id: Optional track match ID for database tracking

        Returns:
            Optimized search query

        Raises:
            Exception: If generation fails
        """
        from utils.text_processing import generate_fallback_search_query

        metadata = {
            "track": spotify_track.get("name", ""),
            "artists": [a["name"] for a in spotify_track.get("artists", [])],
            "album": spotify_track.get("album", {}).get("name", ""),
            "duration": f"{spotify_track.get('duration_ms', 0) // 1000}s",
            "isrc": spotify_track.get("external_ids", {}).get("isrc", "N/A"),
        }

        prompt = f"""Generate the most effective YouTube Music search query for:
        Track: {metadata['track']}
        Artists: {', '.join(metadata['artists'])}
        Album: {metadata['album']}
        Duration: {metadata['duration']}
        ISRC: {metadata['isrc']}
        Respond ONLY with the query."""

        self.logger.debug("Generating search query with LLM")

        response, success, execution_time, error = self._execute_llm_query(
            prompt=prompt,
        )

        # Track the LLM query in the database if database is provided
        if self.db and self.run_id:
            self.db.log_llm_query(
                run_id=self.run_id,
                query_type="search_query",
                prompt=prompt,
                execution_time=execution_time,
                success=success,
                response=response if success else None,
                error_message=error if not success else None,
                track_match_id=track_match_id,
            )

        if success and response:
            query = response.strip().strip('"')
            self.logger.debug(f"Generated LLM query: {query}")
            return query
        else:
            self.logger.warning(f"LLM query failed: {error}, using fallback")
            return generate_fallback_search_query(spotify_track)

    def judge_candidates(
        self,
        spotify_track: Dict[str, Any],
        candidates: list,
        track_match_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Use LLM to select best candidate when scores are ambiguous.

        Args:
            spotify_track: Spotify track data
            candidates: List of YouTube candidate tracks
            track_match_id: Optional track match ID for database tracking

        Returns:
            Best matching candidate

        Raises:
            Exception: If judging fails
        """

        def format_candidate(i: int, c: Dict) -> str:
            from utils.text_processing import safe_get

            title = safe_get(c, ["title"], "Unknown title")
            artists = safe_get(c, ["artists"], [])
            artist = safe_get(artists[0], ["name"], "Unknown") if artists else "Unknown"
            duration = safe_get(c, ["duration"], "?")
            album = safe_get(c, ["album", "name"], "unknown")
            return f"{i}. {title} by {artist} ({duration}) | Album: {album}"

        prompt = f"""
        Analyze this music track matching request. Return JSON with 'index' (0-2) and 'confidence' (0-100).

        Spotify Track:
        - Title: {spotify_track['name']}
        - Artist: {spotify_track['artists'][0]['name']}
        - Album: {spotify_track['album']['name']}
        - Duration: {spotify_track['duration_ms']//1000}s

        YouTube Candidates:
        {json.dumps([format_candidate(i, c) for i, c in enumerate(candidates)], indent=2)}
        """

        self.logger.debug("Judging candidates with LLM")

        response, success, execution_time, error = self._execute_llm_query(
            prompt=prompt, format="json"
        )

        # Track the LLM query in the database if database is provided
        if self.db and self.run_id:
            self.db.log_llm_query(
                run_id=self.run_id,
                query_type="judge",
                prompt=prompt,
                execution_time=execution_time,
                success=success,
                response=response if success else None,
                error_message=error if not success else None,
                track_match_id=track_match_id,
            )

        if success and response:
            try:
                result = json.loads(response)
                index = result.get("index", 0)
                confidence = result.get("confidence", 0)
                self.logger.debug(
                    f"LLM selected candidate {index} (confidence: {confidence}/100)"
                )
                return candidates[index]
            except (json.JSONDecodeError, KeyError, IndexError) as e:
                self.logger.error(f"Failed to parse LLM response: {str(e)}")
                return candidates[0]
        else:
            self.logger.warning(f"LLM judging failed: {error}, using first candidate")
            return candidates[0]

    def _execute_llm_query(
        self, prompt: str, format: Optional[str] = None
    ) -> Tuple[Optional[str], bool, float, Optional[str]]:
        """Execute an LLM query and measure performance.

        Args:
            prompt: Prompt to send to the LLM
            query_type: Type of query for logging
            format: Optional response format (json, etc.)

        Returns:
            Tuple of (response, success, execution_time, error_message)
        """
        start_time = time.time()
        try:
            options = {"temperature": self.temperature, "num_ctx": self.context_size}

            request_params = {"model": self.model, "prompt": prompt, "options": options}

            if format:
                request_params["format"] = format

            response = ollama.generate(**request_params)
            execution_time = time.time() - start_time

            return response["response"], True, execution_time, None
        except Exception as e:
            execution_time = time.time() - start_time
            error_message = str(e)
            self.logger.error(f"LLM query failed: {error_message}")
            return None, False, execution_time, error_message
