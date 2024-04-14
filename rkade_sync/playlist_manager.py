import os
from typing import Any, Dict, List, Tuple

from youtube import YouTubeMusicDownloader


class PlaylistManager:
    def __init__(self, root: str):
        self.ytm_downloader = YouTubeMusicDownloader()
        self.root = root

    def is_artist(self, text):
        return True

    def extract_song_info(self, video_title, artist="test") -> Tuple[str, List[str]]:
        values = list(s.strip() for s in video_title.split("-", 1))
        if len(values) > 1 and artist == "test":
            first_raw, second_raw = values
            song, artist = (
                (second_raw, first_raw)
                if self.is_artist(second_raw)
                else (first_raw, second_raw)
            )
        else:
            song = video_title
        return song, [artist]

    def standardize_playlist(
        self, playlist: str, songs: List[Dict[str, Any]]
    ) -> Dict[str, str]:
        std_playlist = {
            "raw_dir": f"{self.root}/raw/{playlist}",
            "clean_dir": f"{self.root}/clean/{playlist}",
            "songs": [],
        }
        self.ytm_downloader = YouTubeMusicDownloader()
        num_total = len(songs)
        current_interval = 0
        for i, preprocessed in enumerate(songs):
            try:
                perc = (i / num_total * 100) // 10 * 10
                if perc > current_interval:
                    current_interval = perc
                    print(f"{perc}% done searching for {playlist} ({i+1}/{num_total})")
                title, artist, duration_ms = "", "", 0
                video = preprocessed if "feedbackTokens" in preprocessed else None

                if not video:
                    if "inLibrary" in preprocessed:
                        title, artist = self.extract_song_info(preprocessed["title"])
                    else:
                        title, artist = (
                            preprocessed["title"],
                            preprocessed.get("artist", ["lorum"]),
                        )
                    seconds = preprocessed.get("duration_seconds", 0)
                    if seconds == 0:
                        duration_ms = preprocessed.get("duration_ms", 0)
                    else:
                        duration_ms = seconds * 1000
                    youtube_results, result_type = (
                        self.ytm_downloader.song_search_results(title, artist[0])
                    )
                    if not youtube_results:
                        raise Exception("No YTMusic results. Check header auth.")
                    video = self.ytm_downloader.find_best_match(
                        title=title,
                        artist=artist,
                        duration_ms=duration_ms,
                        youtube_results=youtube_results,
                        result_type=result_type,
                    )
                    if result_type == "song":
                        video["title"], video["artist"] = self.extract_song_info(
                            video["title"],
                        )
                        video["album"] = {"name": video["title"]}

                best_video = video

                if "album" not in best_video:
                    album = best_video["title"]
                elif best_video["album"] is None:
                    album = best_video["title"]
                else:
                    album = best_video["album"]["name"]

                song = {
                    "title": best_video["title"],
                    "artist": best_video["artist"],
                    "album": album,
                    "video_id": best_video["videoId"],
                    "thumbnail_url": best_video["thumbnails"][-1]["url"],
                    "filename": f"{title.replace('/','')} - {' & '.join(best_video['artist'])}",
                }
                std_playlist["songs"].append(song)
            except:
                print(f"Failed: {preprocessed}")
        print(f"Done searching for {playlist}")
        return std_playlist

    def download_playlist(self, name, info):
        self.ytm_downloader = YouTubeMusicDownloader()
        os.makedirs(info["raw_dir"], exist_ok=True)
        os.makedirs(info["clean_dir"], exist_ok=True)
        num_total = len(info["songs"])
        current_interval = 0
        for i, song in enumerate(info["songs"]):
            perc = (i / num_total * 100) // 10 * 10
            if perc > current_interval:
                current_interval = perc
                print(f"{perc}% done downloading for {name} ({i+1}/{num_total})")
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
        print(f"Done downloading {name}")
