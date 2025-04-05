"""Main module for the music matcher application."""

import argparse
import sys
import time
from typing import Any, Dict, Optional

from clients.llm_client import LLMClient
from clients.spotify_client import SpotifyClient
from clients.ytmusic_client import YTMusicClient
from config import Config
from database import Database
from matchers.fuzzy_matcher import FuzzyMatcher
from matchers.llm_matcher import LLMMatcher
from utils.logging_utils import setup_logging


class MusicMatcherApp:
    """Main application class for music matching."""

    def __init__(
        self,
        spotify_client_id: str,
        spotify_client_secret: str,
        ytmusic_auth_path: str = "browser.json",
        debug: bool = False,
    ):
        """Initialize music matcher application.

        Args:
            spotify_client_id: Spotify API client ID
            spotify_client_secret: Spotify API client secret
            ytmusic_auth_path: Path to YTMusic auth JSON file
            debug: Enable debug logging
        """
        # Initialize database
        self.db = Database(Config.DATABASE_PATH)

        # Start tracking run
        self.run_id = self.db.start_run(
            {
                "spotify_client_id": spotify_client_id,
                "ytmusic_auth_path": ytmusic_auth_path,
                "debug": debug,
                "config": {
                    k: v for k, v in vars(Config).items() if not k.startswith("_")
                },
            }
        )

        # Set up logging
        log_level = "DEBUG" if debug else Config.LOG_LEVEL
        self.logger = setup_logging(Config.LOG_FILE, log_level, self.db, self.run_id)

        # Initialize clients
        self.logger.info("Initializing clients")
        self.spotify = SpotifyClient(
            spotify_client_id, spotify_client_secret, self.logger
        )
        self.ytmusic = YTMusicClient(ytmusic_auth_path, self.logger)
        self.llm_client = LLMClient(
            model=Config.LLM_MODEL,
            temperature=Config.LLM_TEMPERATURE,
            context_size=Config.LLM_CONTEXT_SIZE,
            logger=self.logger,
            db=self.db,
            run_id=self.run_id,
        )

        # Initialize matchers
        self.logger.info("Initializing matchers")
        self.llm_matcher = LLMMatcher(self.llm_client, self.logger)
        self.fuzzy_matcher = FuzzyMatcher(
            title_weight=Config.TITLE_WEIGHT,
            artist_weight=Config.ARTIST_WEIGHT,
            duration_weight=Config.DURATION_WEIGHT,
            llm_score_threshold=Config.LLM_SCORE_THRESHOLD,
            llm_score_difference=Config.LLM_SCORE_DIFFERENCE,
            logger=self.logger,
        )

        # Set LLM matcher for fuzzy matcher fallback
        self.fuzzy_matcher.set_llm_matcher(self.llm_matcher)

        self.logger.info("Music matcher initialized")

    def __del__(self):
        """Clean up resources on deletion."""
        if hasattr(self, "run_id") and hasattr(self, "db"):
            try:
                self.db.end_run(self.run_id, "COMPLETED")
            except Exception as e:
                # Can't use logger here as it might be gone already
                print(f"Error ending run: {str(e)}")

    def match_track(self, track_id: str) -> Dict[str, Any]:
        """Match a single Spotify track to YouTube Music.

        Args:
            track_id: Spotify track ID

        Returns:
            Best matching YouTube track

        Raises:
            Exception: If matching fails
        """
        self.logger.info(f"Matching track {track_id}")

        try:
            # Get Spotify track data
            spotify_track = self.spotify.get_track(track_id)

            # Generate optimized search query
            query = self.llm_client.generate_query(spotify_track)

            # Search for candidates on YouTube Music
            youtube_results = self.ytmusic.search_tracks(
                query, max_results=Config.MAX_YOUTUBE_RESULTS
            )

            if not youtube_results:
                error_msg = "No YouTube results found"
                self.logger.warning(error_msg)

                # Log to database
                self.db.log_track_match(
                    run_id=self.run_id,
                    spotify_track_id=track_id,
                    spotify_data=spotify_track,
                    success=False,
                    error_message=error_msg,
                )

                return {}

            # Score candidates using fuzzy matching
            scored_results = self.fuzzy_matcher.score_candidates(
                spotify_track, youtube_results
            )

            # Select best match
            best_match = self.fuzzy_matcher.select_best_match(
                spotify_track, scored_results
            )

            # Log match to database
            match_score = scored_results[0][0] if scored_results else None
            self.db.log_track_match(
                run_id=self.run_id,
                spotify_track_id=track_id,
                youtube_track_id=best_match.get("videoId"),
                spotify_data=spotify_track,
                youtube_data=best_match,
                match_score=match_score,
                matcher_used="fuzzy",
                success=True,
            )

            return best_match

        except Exception as e:
            error_msg = f"Error matching track {track_id}: {str(e)}"
            self.logger.error(error_msg)

            # Log error to database
            try:
                self.db.log_track_match(
                    run_id=self.run_id,
                    spotify_track_id=track_id,
                    spotify_data={"id": track_id},
                    success=False,
                    error_message=error_msg,
                )
            except Exception as db_error:
                self.logger.error(f"Failed to log error to database: {str(db_error)}")

            raise

    def match_playlist(
        self, playlist_id: str, max_tracks: Optional[int] = None
    ) -> Dict[str, Any]:
        """Match all tracks in a Spotify playlist.

        Args:
            playlist_id: Spotify playlist ID
            max_tracks: Optional maximum number of tracks to process

        Returns:
            Dictionary of results with statistics

        Raises:
            Exception: If playlist matching fails
        """
        self.logger.info(f"Matching playlist {playlist_id}")
        start_time = time.time()

        try:
            # Get track IDs from playlist
            track_ids = self.spotify.get_playlist_tracks(
                playlist_id, batch_size=Config.SPOTIFY_BATCH_SIZE
            )

            if max_tracks:
                track_ids = track_ids[:max_tracks]

            self.logger.info(f"Processing {len(track_ids)} tracks from playlist")

            # Match each track
            results = []
            success_count = 0

            for i, track_id in enumerate(track_ids):
                try:
                    self.logger.info(
                        f"Processing track {i+1}/{len(track_ids)}: {track_id}"
                    )
                    match = self.match_track(track_id)

                    if match:
                        success_count += 1
                        results.append(
                            {
                                "spotify_id": track_id,
                                "youtube_id": match.get("videoId"),
                                "title": match.get("title"),
                                "success": True,
                            }
                        )
                    else:
                        results.append(
                            {
                                "spotify_id": track_id,
                                "success": False,
                                "error": "No match found",
                            }
                        )

                except Exception as e:
                    self.logger.error(f"Error matching track {track_id}: {str(e)}")
                    results.append(
                        {"spotify_id": track_id, "success": False, "error": str(e)}
                    )

            # Compute statistics
            duration = time.time() - start_time
            stats = {
                "total_tracks": len(track_ids),
                "successful_matches": success_count,
                "failed_matches": len(track_ids) - success_count,
                "success_rate": success_count / len(track_ids) if track_ids else 0,
                "duration_seconds": duration,
                "average_time_per_track": duration / len(track_ids) if track_ids else 0,
            }

            self.logger.info(
                f"Playlist matching completed. Success rate: {stats['success_rate']:.2%}"
            )

            # Update run with statistics
            self.db.end_run(self.run_id, "SUCCESS", stats)

            return {"results": results, "stats": stats}

        except Exception as e:
            error_msg = f"Error matching playlist {playlist_id}: {str(e)}"
            self.logger.error(error_msg)

            # Mark run as failed
            self.db.end_run(self.run_id, "FAILED", {"error": str(e)})

            raise


def main():
    """Command line entry point."""
    parser = argparse.ArgumentParser(
        description="Match Spotify tracks to YouTube Music"
    )
    parser.add_argument("--spotify-id", required=True, help="Spotify client ID")
    parser.add_argument("--spotify-secret", required=True, help="Spotify client secret")
    parser.add_argument(
        "--ytmusic-auth", default="browser.json", help="Path to YTMusic auth file"
    )
    parser.add_argument("--playlist-id", help="Spotify playlist ID to match")
    parser.add_argument("--track-id", help="Spotify track ID to match")
    parser.add_argument(
        "--max-tracks", type=int, help="Maximum tracks to process from playlist"
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    if not args.playlist_id and not args.track_id:
        print("Error: Either --playlist-id or --track-id must be specified")
        sys.exit(1)

    try:
        app = MusicMatcherApp(
            spotify_client_id=args.spotify_id,
            spotify_client_secret=args.spotify_secret,
            ytmusic_auth_path=args.ytmusic_auth,
            debug=args.debug,
        )

        if args.track_id:
            result = app.match_track(args.track_id)
            print(f"Match result: {result}")
        else:
            results = app.match_playlist(args.playlist_id, args.max_tracks)
            print(
                f"Matched {results['stats']['successful_matches']} of {results['stats']['total_tracks']} tracks"
            )
            print(f"Success rate: {results['stats']['success_rate']:.2%}")

    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
