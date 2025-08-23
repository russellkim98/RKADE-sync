"""Client for interacting with the Ollama API."""

import logging
from typing import List, Tuple

import httpx

from .data_models import Track, YouTubeCandidate
from .config import OLLAMA_BASE_URL, OLLAMA_MODEL

logger = logging.getLogger(__name__)


class OllamaClient:
    def __init__(self, base_url: str = OLLAMA_BASE_URL, model: str = OLLAMA_MODEL):
        self.base_url = base_url
        self.model = model
        self.async_client = httpx.AsyncClient()

    async def is_available(self) -> bool:
        """Check if the Ollama service is available."""
        try:
            response = await self.async_client.get(f"{self.base_url}/api/tags", timeout=5)
            response.raise_for_status()
            return True
        except httpx.RequestError as e:
            logger.warning(f"Ollama is not available at {self.base_url}. Reason: {e}")
            return False

    async def generate(self, prompt: str, temperature: float = 0.1) -> str:
        """Generate a response using the Ollama API."""
        if not await self.is_available():
            logger.error("Cannot generate response, Ollama service is unavailable.")
            return ""

        try:
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {"temperature": temperature, "top_p": 0.9, "top_k": 40},
            }
            response = await self.async_client.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=30,
            )
            response.raise_for_status()
            return response.json().get("response", "").strip()
        except httpx.RequestError as e:
            logger.error(f"Ollama API request failed: {e}")
            return ""
        except Exception as e:
            logger.error(f"An unexpected error occurred during generation: {e}")
            return ""

    async def analyze_song_similarity(
        self, spotify_track: Track, youtube_candidates: List[YouTubeCandidate]
    ) -> List[Tuple[YouTubeCandidate, float]]:
        """Use AI to analyze similarity between a Spotify track and YouTube candidates."""
        prompt = self._build_similarity_prompt(spotify_track, youtube_candidates)
        response_text = await self.generate(prompt)

        if not response_text:
            logger.warning("AI generation failed, using fallback similarity.")
            return self._get_fallback_scores(spotify_track, youtube_candidates)

        similarity_scores = self._parse_similarity_response(response_text, youtube_candidates)

        if not similarity_scores:
            logger.warning("AI response parsing failed, using fallback similarity.")
            return self._get_fallback_scores(spotify_track, youtube_candidates)

        similarity_scores.sort(key=lambda x: x[1], reverse=True)
        return similarity_scores

    def _build_similarity_prompt(self, spotify_track: Track, youtube_candidates: List[YouTubeCandidate]) -> str:
        """Builds the prompt for the Ollama API."""
        from .utils import format_duration

        prompt = f"""You are a music expert analyzing song matches. Compare this Spotify track with the following YouTube candidates and rate their similarity.

Spotify Track:
- Title: "{spotify_track.name}"
- Artist: "{spotify_track.artist}"
- Album: "{spotify_track.album}"
- Duration: {format_duration(spotify_track.duration_ms)}

YouTube Candidates:
"""

        for i, candidate in enumerate(youtube_candidates, 1):
            duration_str = f"{candidate.duration_seconds // 60}:{candidate.duration_seconds % 60:02d}"
            prompt += f"""
{i}. Title: "{candidate.title}"
   Artist: "{candidate.artist}"
   Channel: "{candidate.channel_name}"
   Duration: {duration_str}
   Views: {candidate.view_count:,}
   Official: {candidate.is_official}
"""

        prompt += """\nFor each candidate, provide a similarity score from 0.0 to 1.0 based on:
- Title match (exact vs variations, e.g., "live", "official video")
- Artist match (including features, collaborations)
- Duration similarity (within a few seconds is best)
- Channel credibility (official artist channels, VEVO, verified channels)
- Audio quality indicators (explicit mentions of "audio", "lyrics", etc.)

Respond in this exact format for each candidate, and nothing else:
Candidate 1: 0.X - [brief reason]
Candidate 2: 0.X - [brief reason]
...

Be strict with scoring. Only give 0.9+ for near-perfect matches that are likely official audio or video."""
        return prompt

    def _parse_similarity_response(
        self, response_text: str, youtube_candidates: List[YouTubeCandidate]
    ) -> List[Tuple[YouTubeCandidate, float]]:
        """Parses the similarity response from Ollama."""
        similarity_scores = []
        lines = [line.strip() for line in response_text.split("\n") if line.strip()]

        for line in lines:
            if line.startswith("Candidate"):
                try:
                    parts = line.split(":")
                    if len(parts) >= 2:
                        candidate_num_str = parts[0].split()[-1]
                        candidate_num = int(candidate_num_str) - 1

                        score_part = parts[1].strip().split()[0]
                        score = float(score_part)

                        if 0 <= candidate_num < len(youtube_candidates):
                            similarity_scores.append(
                                (youtube_candidates[candidate_num], score)
                            )
                except (ValueError, IndexError) as e:
                    logger.warning(f"Failed to parse AI similarity line: '{line}' - {e}")
                    continue
        return similarity_scores

    def _get_fallback_scores(
        self, spotify_track: Track, youtube_candidates: List[YouTubeCandidate]
    ) -> List[Tuple[YouTubeCandidate, float]]:
        """Helper to generate, sort, and return scores from the fallback method."""
        return sorted(
            [
                (candidate, self._fallback_similarity(spotify_track, candidate))
                for candidate in youtube_candidates
            ],
            key=lambda x: x[1],
            reverse=True,
        )

    def _fallback_similarity(
        self, spotify_track: Track, youtube_candidate: YouTubeCandidate
    ) -> float:
        """Fallback similarity calculation if AI fails."""
        score = 0.0
        spotify_title = spotify_track.name.lower()
        youtube_title = youtube_candidate.title.lower()

        if spotify_title in youtube_title:
            score += 0.4
        elif any(word in youtube_title for word in spotify_title.split() if len(word) > 3):
            score += 0.2

        spotify_artist = spotify_track.artist.lower()
        youtube_artist_full = (youtube_candidate.artist + youtube_candidate.channel_name).lower()

        if spotify_artist in youtube_artist_full:
            score += 0.3

        if spotify_track.duration_ms > 0:
            spotify_seconds = spotify_track.duration_ms / 1000
            duration_diff = abs(spotify_seconds - youtube_candidate.duration_seconds)
            if duration_diff <= 5:
                score += 0.2
            elif duration_diff <= 15:
                score += 0.1

        if youtube_candidate.is_official:
            score += 0.15

        return min(score, 1.0)
