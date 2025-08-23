"""Manages the download of tracks from YouTube."""

import asyncio
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Tuple

import eyed3
import yt_dlp

from .config import DOWNLOAD_DIR, RETRY_ATTEMPTS
from .data_models import Track, YouTubeCandidate

logger = logging.getLogger(__name__)

DOWNLOAD_LOG_PATH = DOWNLOAD_DIR / "downloaded_videos.json"


class DownloadManager:
    def __init__(self):
        self.download_log = self._load_download_log()

    def _load_download_log(self) -> Dict[str, Any]:
        """Loads the download log from a JSON file."""
        if DOWNLOAD_LOG_PATH.exists():
            with open(DOWNLOAD_LOG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"downloaded_ids": []}

    def _save_download_log(self):
        """Saves the download log to a JSON file."""
        with open(DOWNLOAD_LOG_PATH, "w", encoding="utf-8") as f:
            json.dump(self.download_log, f, indent=4)

    def is_downloaded(self, video_id: str) -> bool:
        """Checks if a video has already been downloaded."""
        return video_id in self.download_log["downloaded_ids"]

    async def download_track(
        self, track: Track, candidate: YouTubeCandidate, attempt: int = 1
    ) -> bool:
        """Downloads a single track with retry logic."""
        safe_name = self._safe_filename(f"{track.artist} - {track.name}")
        final_path = DOWNLOAD_DIR / f"{safe_name}.mp3"

        if final_path.exists():
            logger.info(f"✅ Already exists: {final_path.name}")
            return True

        if self.is_downloaded(candidate.video_id):
            logger.info(f"✅ Already downloaded: {track}")
            return True

        if attempt > RETRY_ATTEMPTS:
            logger.error(f"❌ Failed to download after {RETRY_ATTEMPTS} attempts: {track}")
            return False

        loop = asyncio.get_event_loop()
        try:
            output_path = DOWNLOAD_DIR / f"{safe_name}.%(ext)s"

            ydl_opts = {
                "format": "bestaudio[ext=m4a]/bestaudio[ext=mp3]/bestaudio/best",
                "outtmpl": str(output_path),
                "extractaudio": True,
                "audioformat": "mp3",
                "audioquality": "0",
                "embed_thumbnail": True,
                "add_metadata": True,
                "quiet": True,
                "retries": 3,
                "fragment_retries": 3,
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "320",
                    }
                ],
            }

            url = f"https://www.youtube.com/watch?v={candidate.video_id}"
            logger.info(f"⬇️ Downloading: {track} (Quality: {candidate.quality_score:.1f})")

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                await loop.run_in_executor(None, ydl.download, [url])

            self._add_metadata(final_path, track, candidate)

            self.download_log["downloaded_ids"].append(candidate.video_id)
            self._save_download_log()

            logger.info(f"✅ Successfully downloaded: {track}")
            return True

        except yt_dlp.utils.DownloadError as e:
            logger.error(f"❌ yt-dlp download error for {track}: {e}")
            return False
        except Exception as e:
            logger.warning(f"⚠️ Download attempt {attempt} failed for {track}: {e}")
            await asyncio.sleep(2 ** attempt)
            return await self.download_track(track, candidate, attempt + 1)

    def _add_metadata(self, file_path: Path, track: Track, candidate: YouTubeCandidate):
        """Adds ID3 metadata to the downloaded file."""
        try:
            audiofile = eyed3.load(str(file_path))
            if audiofile and audiofile.tag:
                audiofile.tag.title = track.name
                audiofile.tag.artist = track.artist
                audiofile.tag.album = track.album
                audiofile.tag.comments.set(f"Downloaded from: {candidate.channel_name}")
                audiofile.tag.save()
                logger.debug(f"✅ Added metadata to: {file_path.name}")
        except Exception as e:
            logger.warning(f"⚠️ Failed to add metadata to {file_path}: {e}")

    def _safe_filename(self, text: str) -> str:
        """Create a safe filename from text"""
        return "".join(c for c in text if c.isalnum() or c in (" ", "-", "_", ".")).strip()
