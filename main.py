import json
import re
from datetime import datetime
from typing import Dict, List, Optional

import ollama
import pandas as pd
import spotipy
from fuzzywuzzy import fuzz
from Levenshtein import jaro_winkler
from spotipy.oauth2 import SpotifyClientCredentials
from ytmusicapi import YTMusic


class MusicMatcher:
    # Scoring Weights & Thresholds
    TITLE_WEIGHT = 0.5
    ARTIST_WEIGHT = 0.3
    DURATION_WEIGHT = 0.2
    LLM_SCORE_THRESHOLD = 85
    LLM_SCORE_DIFFERENCE = 15
    MAX_YOUTUBE_RESULTS = 10

    def __init__(
        self,
        spotify_client_id: str,
        spotify_client_secret: str,
        ytmusic_auth_path: str = "browser.json",
        debug: bool = False,
    ):
        self.spotify = self._init_spotify(spotify_client_id, spotify_client_secret)
        self.ytmusic = YTMusic(auth=ytmusic_auth_path)
        self.debug = debug
        self.logs: List[Dict] = []

    # === Auth / Client Setup ===

    @staticmethod
    def _init_spotify(client_id: str, client_secret: str) -> spotipy.Spotify:
        credentials = SpotifyClientCredentials(client_id, client_secret)
        return spotipy.Spotify(auth_manager=credentials)

    # === Logging ===

    def _log_debug(self, message: str, divider: bool = False):
        if not self.debug:
            return
        if divider:
            message = f"\n{'=' * 50}\n{message}\n{'=' * 50}"
        print(message)
        self.logs.append({"timestamp": datetime.now(), "message": message})

    def get_debug_logs(self) -> pd.DataFrame:
        return pd.DataFrame(self.logs)

    # === Track Matching ===

    def match_tracks(self, spotify_track: Dict, youtube_results: List[Dict]) -> Dict:
        """Match a Spotify track with the best YouTube Music result."""
        sp_title = self._normalize_text(spotify_track["name"])
        sp_artist = self._normalize_text(spotify_track["artists"][0]["name"])
        sp_duration = spotify_track["duration_ms"] // 1000

        self._log_debug(
            f"MATCHING: {spotify_track['name']} by {spotify_track['artists'][0]['name']} ({sp_duration}s)",
            divider=True,
        )

        scored = [
            self._score_match(sp_title, sp_artist, sp_duration, yt)
            for yt in youtube_results
        ]
        scored.sort(reverse=True, key=lambda x: x[0])
        top_candidates = [track for _, track in scored[:3]]

        self._log_debug("TOP MATCHES:")
        for idx, (score, track) in enumerate(scored[:3], 1):
            self._log_debug(f"{idx}. {track.get('title')} - Score: {score:.1f}")

        # LLM fallback
        top_score = scored[0][0]
        second_score = scored[1][0] if len(scored) > 1 else 0
        if (
            top_score < self.LLM_SCORE_THRESHOLD
            or (top_score - second_score) < self.LLM_SCORE_DIFFERENCE
        ):
            self._log_debug("Triggering LLM fallback...")
            return self._resolve_with_llm(spotify_track, top_candidates)

        return top_candidates[0]

    def _score_match(self, sp_title, sp_artist, sp_duration, yt: Dict) -> tuple:
        yt_title = self._normalize_text(yt.get("title", ""))
        yt_artist = (
            self._normalize_text(yt["artists"][0]["name"]) if yt.get("artists") else ""
        )
        yt_duration = yt.get("duration_seconds", 0)

        title_score = fuzz.token_sort_ratio(sp_title, yt_title)
        artist_score = jaro_winkler(sp_artist, yt_artist) * 100
        duration_score = max(0, 100 - abs(sp_duration - yt_duration))

        total_score = (
            title_score * self.TITLE_WEIGHT
            + artist_score * self.ARTIST_WEIGHT
            + duration_score * self.DURATION_WEIGHT
        )

        if self.debug:
            self._log_debug(
                f"{yt.get('title', '')} | Artist: {yt_artist} | Duration: {yt_duration}s\n"
                f"→ Title: {title_score:.1f}, Artist: {artist_score:.1f}, Duration: {duration_score:.1f}, Total: {total_score:.1f}\n"
                + "-" * 40
            )

        return total_score, yt

    # === LLM Matching ===

    def _resolve_with_llm(self, spotify_track: Dict, candidates: List[Dict]) -> Dict:
        def format_candidate(i: int, c: Dict) -> str:
            return f"{i}. {self._safe_get(c, ['title'], 'Unknown')} by {self._safe_get(c, ['artists', 0, 'name'], 'Unknown')} ({self._safe_get(c, ['duration'], '?')}) | Album: {self._safe_get(c, ['album', 'name'], 'unknown')}"

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

        self._log_debug(f"LLM PROMPT:\n{prompt}", divider=True)

        try:
            response = ollama.generate(
                model="gemma3:12b",
                prompt=prompt,
                format="json",
                options={"temperature": 0.3, "num_ctx": 4096},
            )
            result = json.loads(response["response"])
            self._log_debug(f"LLM RESPONSE:\n{response}", divider=True)
            return candidates[result["index"]]
        except Exception as e:
            self._log_debug(f"LLM failed: {e}, using top candidate")
            return candidates[0]

    # === Search Query Generation ===

    def generate_search_query(self, spotify_track: Dict) -> str:
        """Use LLM or fallback to generate a YTMusic search query."""
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

        try:
            response = ollama.generate(
                model="gemma3:12b", prompt=prompt, options={"temperature": 0.2}
            )
            query = response["response"].strip().strip('"')
            self._log_debug(f"Generated LLM query: {query}")
            return query
        except Exception as e:
            self._log_debug(f"LLM query failed: {e}, using fallback")
            return self._fallback_search_query(spotify_track)

    def _fallback_search_query(self, track: Dict) -> str:
        """Basic heuristic fallback for search query generation."""
        artists = [a["name"] for a in track.get("artists", [])]
        album = track.get("album", {}).get("name", "")
        keywords = {"remaster", "deluxe", "live", "version", "edit", "mix", "bonus"}

        parts = [track.get("name", ""), artists[0] if artists else ""]
        if len(artists) > 1:
            parts.append("feat. " + ", ".join(artists[1:]))
        if any(k in album.lower() for k in keywords):
            parts.append(album)

        return re.sub(r"\s+", " ", " ".join(parts)).strip()

    # === Playlist Utilities ===

    def get_playlist_tracks(
        self, playlist_id: str, market: Optional[str] = None
    ) -> List[str]:
        """Retrieve track IDs from a Spotify playlist."""
        tracks = []
        offset, limit = 0, 100

        while True:
            result = self.spotify.playlist_items(
                playlist_id,
                fields="items(track(id))",
                limit=limit,
                offset=offset,
                market=market,
                additional_types=["track"],
            )
            if not result:
                raise Exception("Results of playlist items are empty")
            items = result.get("items", [])
            tracks += [i["track"]["id"] for i in items if i.get("track", {}).get("id")]
            if len(items) < limit:
                break
            offset += limit

        return tracks

    def get_rekordbox_playlists(self, user_id: str) -> Dict[str, str]:
        """Find playlists that look like rekordbox exports."""
        playlists = self.spotify.user_playlists(user_id)
        if not playlists:
            raise Exception("Playlists are empty")
        return {
            p["name"]: p["id"] for p in playlists["items"] if "rekordbox_" in p["name"]
        }

    # === Helpers ===

    @staticmethod
    def _normalize_text(text: str) -> str:
        return re.sub(r"[^a-z0-9]", "", text.lower())

    @staticmethod
    def _safe_get(d: dict, keys: List, default=None):
        for key in keys:
            try:
                d = d[key]
            except (KeyError, IndexError, TypeError):
                return default
        return d
