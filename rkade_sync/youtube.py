import os
from typing import Any, Dict, List

import eyed3
import Levenshtein as lev
import requests
from eyed3.id3 import frames
from pydub import AudioSegment
from pytube import YouTube
from ytmusicapi import YTMusic


class YouTubeMusicDownloader:
    def __init__(self, headers: Dict[str, str]):
        self.headers = headers
        self.client = YTMusic(auth=self.headers)

    def song_search_results(
        self, title: str, artist: str
    ) -> List[Dict[str, Any]] | None:
        """
        Search for songs on YouTube Music.

        Args:
            title (str): The title of the song.
            artist (str): The artist of the song.

        Returns:
            List[Dict[str, Any]] | None: A list of search results or None if no results found.
        """
        response = self.client.search(f"{title} by {artist}", filter="songs")
        return response if response else None

    def find_best_match(
        self, title, artist, duration_ms, youtube_results: List[Dict[str, Any]]
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
            song["duration_ms"] = song["duration_seconds"] * 1000
            song["artist"] = [artist["name"] for artist in song["artists"]]

            title_distance = lev.distance(title, song["title"]) / len(title)
            artist_distance = lev.distance(artist, song["artist"][0]) / len(artist)
            duration_distance = abs(duration_ms - song["duration_ms"]) / 1000
            distance = title_distance + artist_distance + duration_distance

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
            tags={"artist": artists, "album": album, "playlist": playlist},
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
                print("Thumbnail set successfully.")
            else:
                print("Audio file not found or does not contain tags.")
        else:
            print("Failed to fetch thumbnail.")
