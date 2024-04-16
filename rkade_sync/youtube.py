import hashlib
import os
import time
from typing import Any, Dict, List, Tuple

import browser_cookie3
import eyed3
import requests
from config import YOUTUBE_MUSIC_COOKIE_NAMES, YOUTUBE_MUSIC_HEADERS
from eyed3.id3 import frames
from pydub import AudioSegment, effects
from pytube import YouTube
from thefuzz import fuzz
from ytmusicapi import YTMusic


def get_youtube_cookies(cookie_jar, cookie_names):
    return {c.name: c.value for c in cookie_jar if c.name in cookie_names}


def generate_sapisidhash_header(SAPISID, origin="https://www.youtube.com"):
    time_now = round(time.time())
    sapisidhash = hashlib.sha1(f"{time_now} {SAPISID} {origin}".encode()).hexdigest()
    return f"SAPISIDHASH {time_now}_{sapisidhash}"


def generate_ytm_cookies():
    cookie_jar = browser_cookie3.chrome()
    cookies_youtube_music = get_youtube_cookies(cookie_jar, YOUTUBE_MUSIC_COOKIE_NAMES)
    YOUTUBE_MUSIC_HEADERS["authorization"] = generate_sapisidhash_header(
        cookies_youtube_music["SAPISID"]
    )
    YOUTUBE_MUSIC_HEADERS["cookie"] = "; ".join(
        [f"{k}={v}" for k, v in cookies_youtube_music.items()]
    )

    return YOUTUBE_MUSIC_HEADERS


class YouTubeMusicDownloader:
    def __init__(self):
        self.headers = generate_ytm_cookies()
        self.client = YTMusic(auth=self.headers)

    def get_youtube_playlists(self, fuzzy: str = "rekordbox"):
        all_playlists = self.client.get_library_playlists()
        return {
            playlist["title"]: self.client.get_playlist(
                playlist["playlistId"], limit=400
            )["tracks"]
            for playlist in all_playlists
            if fuzzy in playlist["title"]
        }

    def song_search_results(
        self, title: str, artists: List[str], video_type: str
    ) -> List[Dict[str, Any]]:
        """
        Search for songs on YouTube Music.

        Args:
            title (str): The title of the song.
            artist (str): The artist of the song.

        Returns:
            List[Dict[str, Any]] | None: A list of search results or None if no results found.
        """
        artist = " & ".join(artists)
        response = self.client.search(f"{title} by {artist}", filter=video_type)
        return response

    def find_best_match_yt(
        self,
        title: str,
        artist: List[str],
        duration_ms: int,
        yt_results: List[Dict[str, Any]],
        tolerance: float = 0.8,
    ) -> Dict[str, Any]:
        best_score = float("-inf")
        best_result = {}
        query_title = f"{title} - {artist[0]}"

        for video in yt_results:

            video_title = video.get("title", title)
            distance_title = (
                fuzz.partial_token_sort_ratio(query_title, video_title) / 100
            )
            if distance_title < tolerance:
                continue

            video_duration_ms = max(
                [video.get("duration_seconds", -1) * 1000, video.get("duration_ms", 0)]
            )
            distance_duration = (
                1 - abs(duration_ms - video_duration_ms) / duration_ms / 100
            )
            if distance_duration < tolerance:
                continue
            score = distance_title * distance_duration

            if len(video.get("album", [])) < 1:
                album = title
            else:
                album = video["album"]["name"]
            result = dict(
                title=title,
                artist=artist,
                duration_ms=video_duration_ms,
                album=album,
                video_id=video["videoId"],
                thumbnail_url=video["thumbnails"][-1]["url"],
                filename=f"{title} - {' & '.join(artist)}".replace("/", "|"),
            )
            if score > best_score:
                best_score = score
                best_result = result

        return best_result

    def find_best_match_ytm(
        self,
        title: str,
        artist: List[str],
        duration_ms: int,
        ytm_results: List[Dict[str, Any]],
        tolerance: float = 0.8,
    ) -> Dict[str, Any]:

        best_score = float("-inf")
        best_result = {}
        for video in ytm_results:

            video_title = video.get("title", title)
            distance_title = fuzz.partial_ratio(title, video_title) / 100
            if distance_title < tolerance:
                continue

            yt_artist = video.get("artists", [])
            video_artist = (
                [a["name"] for a in yt_artist] if len(yt_artist) > 0 else artist
            )

            distance_artist = fuzz.partial_ratio(artist[0], video_artist[0]) / 100
            if distance_artist < tolerance:
                continue

            video_duration_ms = max(
                [video.get("duration_seconds", -1) * 1000, video.get("duration_ms", 0)]
            )
            distance_duration = (
                1 - abs(duration_ms - video_duration_ms) / duration_ms / 100
            )
            if distance_duration < tolerance:
                continue

            score = distance_title * distance_artist * distance_duration
            result = dict(
                title=video_title,
                artist=video_artist,
                album=video["album"]["name"],
                duration_ms=video_duration_ms,
                video_id=video["videoId"],
                thumbnail_url=video["thumbnails"][-1]["url"],
                filename=f"{video_title} - {' & '.join(video_artist)}".replace(
                    "/", "|"
                ),
            )

            if score > best_score:
                best_score = score
                best_result = result
        return best_result

    def download_audio(self, video_id: str, output_path: str, filename: str) -> str:
        """
        Download audio from YouTube.

        Args:
            video_id (str): YouTube video ID.
            output_path (str): Path to save the downloaded audio.
            filename (str): Name of the downloaded audio file.

        Returns:
            str: Path to the downloaded audio file.
        """
        youtube = YouTube(
            f"https://music.youtube.com/watch?v={video_id}", use_oauth=True
        )
        try:
            stream = youtube.streams.filter(only_audio=True).order_by("abr").last()
        except Exception as e:
            return f"Exception: {e}"
        if stream is None:
            return "No stream available"
        raw_fp = stream.download(
            output_path=output_path, filename=f"{filename}.{stream.subtype}"
        )
        return raw_fp

    def convert_to_mp3(
        self,
        raw_file_path: str,
        output_dir: str,
        title: str,
        artists: List[str],
        album: str,
        playlist: str,
    ) -> str:
        """
        Convert audio to mp3 format.

        Args:
            raw_file_path (str): Path to the raw audio file.
            output_dir (str): Path to save the converted mp3 file.
            title (str): Title of the song.
            artist (str): Artist of the song.
            album (str): Album name.
            playlist (str): Playlist name.

        Returns:
            str: Path to the converted mp3 file.
        """
        raw_audio = effects.normalize(AudioSegment.from_file(raw_file_path))
        final_fp = os.path.join(output_dir, f"{title}.mp3")
        raw_audio.export(
            final_fp,
            format="mp3",
            bitrate="256k",
            tags={"artist": "; ".join(artists), "album": album, "playlist": playlist},
        )
        return final_fp

    def set_thumbnail(self, url: str, audio_path: str) -> None:
        """
        Set thumbnail for the audio file.

        Args:
            url (str): URL of the thumbnail image.
            audio_path (str): Path to the audio file.
        """
        response = requests.get(url)
        if response.status_code == 200:
            audiofile = eyed3.load(audio_path)
            if audiofile and audiofile.tag:
                audiofile.tag.images.set(
                    frames.ImageFrame.FRONT_COVER,
                    response.content,
                    "image/jpeg",
                )
                audiofile.tag.save()
            else:
                print("Audio file not found or does not contain tags.")
        else:
            print("Failed to fetch thumbnail.")
