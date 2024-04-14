import hashlib
import os
import time
from typing import Any, Dict, List, Tuple

import browser_cookie3
import eyed3
import Levenshtein as lev
import requests
from config import YOUTUBE_MUSIC_COOKIE_NAMES, YOUTUBE_MUSIC_HEADERS
from eyed3.id3 import frames
from pydub import AudioSegment
from pytube import YouTube
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
        self, title: str, artist: str
    ) -> Tuple[List[Dict[str, Any]], str]:
        """
        Search for songs on YouTube Music.

        Args:
            title (str): The title of the song.
            artist (str): The artist of the song.

        Returns:
            List[Dict[str, Any]] | None: A list of search results or None if no results found.
        """
        response = self.client.search(f"{title} by {artist}", filter="songs")
        artists = set(artist["name"] for r in response for artist in r["artists"])
        if artist.lower() not in [a.lower() for a in artists]:
            return self.client.search(f"{title} by {artist}", filter="videos"), "video"
        return response, "song"

    def find_best_match(
        self,
        title: str,
        artist: List[str],
        duration_ms: int,
        youtube_results: List[Dict[str, Any]],
        result_type: str,
    ) -> Dict[str, Any]:
        """
        Find the best matching song on YouTube Music.

        Args:
            song_info (Dict[str, Any]): Information about the song from Spotify.
            youtube_results (List[Dict[str, Any]]): List of search results from YouTube Music.

        Returns:
            Dict[str, Any]: The best matching song.
        """
        best_video = youtube_results[0]
        best_video["duration_ms"] = best_video["duration_seconds"] * 1000
        best_video["artist"] = [artist["name"] for artist in best_video["artists"]]
        best_distance = float("inf")

        for song in youtube_results:
            if result_type == "song":
                if "duration_seconds" not in song:
                    song["duration_ms"] = duration_ms
                else:
                    song["duration_ms"] = song["duration_seconds"] * 1000
                if "artists" not in song:
                    song["artist"] = artist
                else:
                    song["artist"] = [
                        artist["name"]
                        for artist in song["artists"]
                        if artist["id"] is not None
                    ]
                    if len(song["artist"]) < 1:
                        song["artist"] = artist

                try:
                    title_distance = lev.distance(title, song["title"]) / len(title)
                    artist_distance = lev.distance(artist, song["artist"][0]) / len(
                        artist
                    )
                    duration_distance = abs(duration_ms - song["duration_ms"]) / 1000
                    distance = title_distance + artist_distance + duration_distance
                except:
                    raise Exception(f"Get best video: {song}")
            else:
                distance = lev.distance(title, song["title"]) / len(title)

            if distance < best_distance:
                best_distance = distance
                best_video = song

        return best_video

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
        stream = youtube.streams.filter(only_audio=True).order_by("abr").last()
        if not stream:
            return "Couldn't find stream"
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
        raw_audio = AudioSegment.from_file(raw_file_path)
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
