import os
from typing import Any, Dict, List, Tuple

from youtube import YouTubeMusicDownloader


class PlaylistManager:
    def __init__(self, root: str):
        self.ytm_downloader = YouTubeMusicDownloader()
        self.root = root

    def is_artist(self, text):
        return True

    def extract_song_info(
        self, video_title: str, channel_name: str
    ) -> Tuple[str, List[str]]:
        values = list(s.strip() for s in video_title.split("-", 1))
        if len(values) > 1:
            first_raw, second_raw = values
            song, artist = (
                (second_raw, first_raw)
                if self.is_artist(second_raw)
                else (first_raw, second_raw)
            )
        else:
            song = video_title
            artist = channel_name
        return song, [artist]

    def get_song_source(self, song: Dict[str, Any]) -> str:

        if "videoType" in song:
            if song["videoType"] == "MUSIC_VIDEO_TYPE_ATV":
                return "yt_music"
            if song["videoType"] == "MUSIC_VIDEO_TYPE_UGC":
                return "yt_video"
        if "artist" in song:
            return "spotify"

        return "unmatched"

    def _standardize_song(
        self, title: str, artists: List[str], duration_ms: int
    ) -> Dict[str, Any]:
        results = self.ytm_downloader.song_search_results(title, artists, "songs")
        best_video = self.ytm_downloader.find_best_match_ytm(
            title, artists, duration_ms, results
        )
        if len(best_video) < 1:
            results = self.ytm_downloader.song_search_results(title, artists, "videos")
            best_video = self.ytm_downloader.find_best_match_yt(
                title, artists, duration_ms, results
            )

        return best_video

    def standardize_song(self, song: Dict[str, Any]) -> Dict[str, Any]:
        match self.get_song_source(song):
            case "spotify":
                std_song = self._standardize_song(
                    song["title"], song["artist"], song["duration_ms"]
                )
            case "yt_music":
                std_song = self.ytm_downloader.find_best_match_ytm(
                    song["title"],
                    song["artists"][0]["name"],
                    song["duration_seconds"] * 1000,
                    [song],
                )
            case _:
                title, artists = self.extract_song_info(
                    song["title"], str(song["artists"][0]["name"])
                )
                std_song = self._standardize_song(
                    title, artists, song["duration_seconds"] * 1000
                )
        return std_song

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
            """
            For each song, do the following
            1. Check whether it's a youtube or spotify type json
                This is done with the `video_id`
            2. If spotify, need to search on youtube.
            3. If Youtube, need to check whether video or YTM format
            4. If YTM, then use as is
            5. if video, need to search on youtube (same flow as 2)
            """
            perc = (i / num_total * 100) // 10 * 10
            if perc > current_interval:
                current_interval = perc
                print(f"{perc}% done searching for {playlist} ({i+1}/{num_total})")
            try:
                s = self.standardize_song(preprocessed)
                s["info_status"] = "success"
            except Exception as e:
                print(f"Failed: {preprocessed}. Error: {e}")
                preprocessed["info_status"] = "failed"
                s = preprocessed

            std_playlist["songs"].append(s)
        print(f"Done searching for {playlist}")
        return std_playlist

    def download_song(self, song, raw_dir: str, clean_dir: str, playlist_name: str):
        try:
            raw_path = self.ytm_downloader.download_audio(
                video_id=song["video_id"],
                output_path=raw_dir,
                filename=song["filename"],
            )
        except:
            print(f"Failed to download audio for {song}")
            return "failed", "failed"

        try:
            clean_path = self.ytm_downloader.convert_to_mp3(
                raw_path,
                clean_dir,
                song["filename"],
                song["artist"],
                song["album"],
                playlist_name,
            )
        except:
            print(f"Failed to convert audio for {song}")
            return "failed", "failed"
        try:
            self.ytm_downloader.set_thumbnail(song["thumbnail_url"], clean_path)
        except:
            print(f"Failed to set thumbnail for {song}")
            return "failed", "failed"
        return raw_path, clean_path

    def download_playlist(self, name, info) -> List[Dict[str, Any]]:
        self.ytm_downloader = YouTubeMusicDownloader()
        songs = []
        os.makedirs(info["raw_dir"], exist_ok=True)
        os.makedirs(info["clean_dir"], exist_ok=True)
        num_total = len(info["songs"])
        current_interval = 0
        for i, song in enumerate(info["songs"]):
            if song["info_status"] == "failure":
                raw_path = "na"
                clean_path = "na"
            else:
                perc = (i / num_total * 100) // 10 * 10
                if perc > current_interval:
                    current_interval = perc
                    print(f"{perc}% done downloading for {name} ({i+1}/{num_total})")
                raw_path, clean_path = self.download_song(
                    song, info["raw_dir"], info["clean_dir"], name
                )
            song["raw_path"] = raw_path
            song["clean_path"] = clean_path
            songs.append(song)

        print(f"Done downloading {name}")
        return songs
