"""Main entry point for the music sync application."""

import argparse
import asyncio
import logging
from typing import List, Tuple

from .config import SIMILARITY_THRESHOLD, MAX_WORKERS
from .data_models import Track, YouTubeCandidate
from .download_manager import DownloadManager
from .logging_config import setup_logging
from .ollama_client import OllamaClient
from .spotify_client import SpotifyManager
from .youtube_client import YouTubeMusicManager

logger = logging.getLogger(__name__)


class MusicSyncOrchestrator:
    def __init__(self):
        self.spotify = SpotifyManager()
        self.ytmusic = YouTubeMusicManager()
        self.downloader = DownloadManager()
        self.ollama = OllamaClient()

    async def sync_music_library(self, include_liked=True, include_playlists=False):
        """Main synchronization process."""
        logger.info("🎵 Starting Music Library Sync...")

        if not self.spotify.authenticate() or not self.ytmusic.authenticate():
            logger.error("Authentication failed. Exiting.")
            return

        spotify_tracks = []
        if include_liked:
            spotify_tracks.extend(self.spotify.get_liked_songs())
        if include_playlists:
            spotify_tracks.extend(self.spotify.get_all_playlists())

        unique_spotify_tracks = self._deduplicate_tracks(spotify_tracks)
        logger.info(f"📊 Processing {len(unique_spotify_tracks)} unique Spotify tracks")

        matches_found = []
        no_matches = []

        for track in unique_spotify_tracks:
            logger.info(f"🔍 Processing: {track}")
            candidates = await self.ytmusic.search_candidates(track)

            if not candidates:
                logger.warning(f"⚠️ No YouTube candidates found for: {track}")
                no_matches.append(track)
                continue

            if await self.ollama.is_available():
                ai_matches = await self.ollama.analyze_song_similarity(track, candidates)
                if ai_matches and ai_matches[0][1] >= SIMILARITY_THRESHOLD:
                    best_candidate, similarity_score = ai_matches[0]
                    logger.info(f"🤖 AI Match found (similarity: {similarity_score:.2f}): {best_candidate}")
                    matches_found.append((track, best_candidate, similarity_score))
                else:
                    logger.warning(f"🤖 AI similarity too low for: {track}")
                    no_matches.append(track)
            else:
                best_candidate = candidates[0]
                logger.info(f"🎯 Quality-based match: {best_candidate} (score: {best_candidate.quality_score:.1f})")
                matches_found.append((track, best_candidate, 0.8))  # Assumed similarity

        logger.info(f"✅ Found {len(matches_found)} matches, {len(no_matches)} without matches")

        if matches_found:
            logger.info("⬇️ Starting downloads...")
            await self._download_matches(matches_found)

    def _deduplicate_tracks(self, tracks: List[Track]) -> List[Track]:
        """Remove duplicate tracks based on name and artist."""
        seen = set()
        unique_tracks = []
        for track in tracks:
            signature = f"{track.name.lower().strip()}|{track.artist.lower().strip()}"
            if signature not in seen:
                seen.add(signature)
                unique_tracks.append(track)
        logger.info(f"🔄 Deduplicated {len(tracks)} -> {len(unique_tracks)} tracks")
        return unique_tracks

    async def _download_matches(self, matches: List[Tuple[Track, YouTubeCandidate, float]]):
        """Download all matched tracks with a semaphore for concurrency control."""
        semaphore = asyncio.Semaphore(MAX_WORKERS)

        async def download_with_semaphore(match_data):
            async with semaphore:
                track, candidate, _ = match_data
                await self.downloader.download_track(track, candidate)

        tasks = [download_with_semaphore(match) for match in matches]
        await asyncio.gather(*tasks)


def main():
    """Main function to run the CLI."""
    parser = argparse.ArgumentParser(description="Sync your Spotify music to a local library.")
    parser.add_argument("--liked", action="store_true", help="Sync liked songs.")
    parser.add_argument("--playlists", action="store_true", help="Sync songs from playlists.")
    parser.add_argument("--all", action="store_true", help="Sync both liked songs and playlists.")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"], help="Set the logging level.")

    args = parser.parse_args()

    setup_logging(logging.getLevelName(args.log_level))

    if args.all:
        include_liked = True
        include_playlists = True
    else:
        include_liked = args.liked
        include_playlists = args.playlists

    if not include_liked and not include_playlists:
        parser.error("You must specify at least one source to sync from: --liked, --playlists, or --all.")

    orchestrator = MusicSyncOrchestrator()
    asyncio.run(orchestrator.sync_music_library(include_liked, include_playlists))


if __name__ == "__main__":
    main()
