"""Client for interacting with the YouTube Music API."""

import logging
import asyncio
from typing import List, Optional

from ytmusicapi import YTMusic

from .config import YTMUSIC_AUTH_TOKEN, MAX_YT_CANDIDATES, QUALITY_WEIGHTS
from .data_models import Track, YouTubeCandidate

logger = logging.getLogger(__name__)


class YouTubeMusicManager:
    def __init__(self):
        self.client = None

    def authenticate(self):
        """Initialize YouTube Music client."""
        try:
            if YTMUSIC_AUTH_TOKEN:
                self.client = YTMusic(YTMUSIC_AUTH_TOKEN)
                logger.info("✅ YouTube Music authenticated with token")
            else:
                self.client = YTMusic()
                logger.info("✅ YouTube Music initialized (public access only)")
            return True
        except Exception as e:
            logger.error(f"❌ YouTube Music initialization failed: {e}")
            return False

    async def search_candidates(self, track: Track) -> List[YouTubeCandidate]:
        """Search for multiple candidates for a track with quality assessment."""
        if not self.client:
            logger.error("YouTube Music client not initialized. Please authenticate first.")
            return []

        loop = asyncio.get_event_loop()
        try:
            search_queries = [
                f"{track.artist} {track.name}",
                f"{track.name} {track.artist}",
                f'"{track.name}" "{track.artist}"'
            ]

            seen_video_ids = set()
            candidates = []

            for query in search_queries:
                if len(candidates) >= MAX_YT_CANDIDATES:
                    break

                for result_type in ["songs", "videos"]:
                    if len(candidates) >= MAX_YT_CANDIDATES:
                        break

                    results = await loop.run_in_executor(
                        None, self.client.search, query, result_type, MAX_YT_CANDIDATES - len(candidates)
                    )
                    for result in results:
                        if result["videoId"] not in seen_video_ids:
                            candidate = self._create_candidate_from_result(result, result_type)
                            if candidate:
                                candidates.append(candidate)
                                seen_video_ids.add(result["videoId"])

            if candidates:
                for candidate in candidates:
                    candidate.quality_score = self._calculate_quality_score(candidate, track)
                candidates.sort(key=lambda x: x.quality_score, reverse=True)

            logger.info(f"Found {len(candidates)} candidates for: {track}")
            return candidates[:MAX_YT_CANDIDATES]

        except Exception as e:
            logger.error(f"❌ Error during search for {track}: {e}")
            return []

    def _create_candidate_from_result(
        self, result: dict, result_type: str
    ) -> Optional[YouTubeCandidate]:
        """Create a YouTubeCandidate from search result"""
        try:
            if not result or "videoId" not in result:
                return None

            video_id = result["videoId"]
            title = result.get("title", "Unknown Title")
            duration_seconds = self._parse_duration(result.get("duration"))
            view_count = self._parse_view_count(result.get("views"))

            if result_type == "song":
                artists = result.get("artists", [])
                artist = (
                    ", ".join([a.get("name", "") for a in artists])
                    if artists
                    else "Unknown Artist"
                )
                channel_name = artist
            else:  # video
                channel_name = result.get("channel", {}).get("name", "Unknown Channel")
                artist = channel_name

            is_official = (
                "official" in channel_name.lower()
                or "vevo" in channel_name.lower()
                or "topic" in channel_name.lower()
            )
            is_music = (
                result_type == "song"
                or "audio" in title.lower()
                or "official music" in title.lower()
            )

            return YouTubeCandidate(
                video_id=video_id,
                title=title,
                artist=artist,
                duration_seconds=duration_seconds,
                view_count=view_count,
                channel_name=channel_name,
                is_official=is_official,
                is_music=is_music,
                quality_score=0.0,
            )
        except Exception as e:
            logger.error(f"Error creating candidate: {e}")
            return None

    def _parse_duration(self, duration_str: Optional[str]) -> int:
        """Convert duration string to seconds."""
        if not duration_str:
            return 0
        parts = list(map(int, duration_str.split(":")))
        if len(parts) == 2:
            return parts[0] * 60 + parts[1]
        if len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
        return 0

    def _parse_view_count(self, view_count_str: Optional[str]) -> int:
        """Convert view count string to an integer."""
        if not view_count_str:
            return 0
        return int(view_count_str.replace(" views", "").replace(",", ""))

    def _calculate_quality_score(self, candidate: YouTubeCandidate, track: Track) -> float:
        """Calculate quality score for a candidate based on various factors."""
        score = 0.0
        quality_checks = {
            "official_artist": candidate.is_official and candidate.artist.lower() in track.artist.lower(),
            "topic_channel": "topic" in candidate.channel_name.lower(),
            "verified_channel": "vevo" in candidate.channel_name.lower() or "official" in candidate.channel_name.lower(),
            "exact_duration": track.duration_ms > 0 and abs(track.duration_ms / 1000 - candidate.duration_seconds) / (track.duration_ms / 1000) < 0.05,
            "high_views": candidate.view_count > 1000000,
            "audio_quality": any(term in candidate.title.lower() for term in ["hq", "high quality", "hd audio"]),
            "is_music": candidate.is_music,
        }

        for check, is_true in quality_checks.items():
            if is_true:
                score += QUALITY_WEIGHTS.get(check, 0)

        return score
