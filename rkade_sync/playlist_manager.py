import os
from typing import Any, Dict, List

from youtube import YouTubeMusicDownloader


class PlaylistManager:
    def __init__(self, ytm_downloader: YouTubeMusicDownloader, root: str):
        self.ytm_downloader = ytm_downloader
        self.root = root

    def is_artist(self, text):
        return True

    def extract_song_info(self, video_title):
        first_raw, second_raw = (s.strip() for s in video_title.split("-", 1))
        song, artist = (
            (second_raw, first_raw)
            if self.is_artist(second_raw)
            else (first_raw, second_raw)
        )
        return song, artist, song

    def standardize_playlist(
        self, playlist: str, songs: List[Dict[str, Any]]
    ) -> Dict[str, str]:
        std_playlist = {
            "raw_dir": f"{self.root}/raw/{playlist}",
            "clean_dir": f"{self.root}/clean/{playlist}",
            "songs": [],
        }

        for preprocessed in songs:
            title, artist, album, duration_ms = "", "", "", 0
            video = preprocessed if "feedbackTokens" in preprocessed else None

            if not video:
                if "inLibrary" in preprocessed:
                    title, artist, album = self.extract_song_info(preprocessed["title"])
                    duration_ms = preprocessed.get("duration_seconds", 0) * 1000
                else:
                    title, artist, album = (
                        preprocessed["title"],
                        preprocessed.get("artist", ""),
                        preprocessed.get("album", ""),
                    )
                    duration_ms = preprocessed.get("duration_ms", 0)
                youtube_results = self.ytm_downloader.song_search_results(title, artist)
                if not youtube_results:
                    raise Exception("No YTMusic results. Check header auth.")
                video = self.ytm_downloader.find_best_match(
                    title=title,
                    artist=artist,
                    duration_ms=duration_ms,
                    youtube_results=youtube_results,
                )

            if (
                title not in video["title"]
                and abs((duration_ms - video["duration_ms"]) / duration_ms) > 0.2
            ):
                best_video = preprocessed
            else:
                best_video = video

            song = {
                "title": best_video["title"],
                "artist": best_video["artist"],
                "album": album,
                "video_id": best_video["videoId"],
                "thumbnail_url": best_video["thumbnails"][-1]["url"],
                "filename": f"{title} - {artist}",
            }
            std_playlist["songs"].append(song)
        return std_playlist

    def download_playlist(self, name, info):
        os.makedirs(info["raw_dir"], exist_ok=True)
        os.makedirs(info["clean_dir"], exist_ok=True)
        for song in info["songs"]:
            raw_path = self.ytm_downloader.download_audio(
                video_id=song["video_id"],
                output_path=info["raw_dir"],
                filename=song["filename"],
            )
            clean_path = self.ytm_downloader.convert_to_mp3(
                raw_path,
                info["clean_dir"],
                song["filename"],
                song["artist"],
                song["album"],
                name,
            )
            self.ytm_downloader.set_thumbnail(song["thumbnail_url"], clean_path)
