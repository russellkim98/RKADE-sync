from dataclasses import dataclass
from pathlib import Path

from helpers.utils import get_song_title_artist
from pydub import AudioSegment
from pytube import Playlist, YouTube
from tqdm.auto import tqdm


@dataclass
class YouTubeVideo:
    video_id: str
    track: str
    artist: str
    album: str
    playlist: str
    comments: str
    thumbnail_url: str

    def download_mp3(self, raw_directory, final_directory) -> str:
        youtube = YouTube(f"https://music.youtube.com/watch?v={self.video_id}")
        stream = youtube.streams.filter(only_audio=True).order_by("abr").last()
        if not stream:
            raise Exception("No valid streams")
        raw_file_path = stream.download(
            output_path=raw_directory, filename=f"{self.track}.{stream.subtype}"
        )
        print("downloaded stream")
        final_file_path = f"{final_directory}/{self.track}.mp3"
        raw_audio = AudioSegment.from_file(raw_file_path)
        print(f"created audio segment, exporting to {final_file_path}")
        return raw_audio.export(
            final_file_path,
            format="mp3",
            bitrate="256k",
            tags={
                "artist": self.artist,
                "album": self.album,
                "playlist": self.playlist,
                "comments": self.comments,
            },
        )


def get_spotify_videos(sp_playlists, ytm_client):
    playlist_map = {}
    for playlist, songs in sp_playlists.items():
        print(f"locating spotify video_ids for {playlist}...")
        videos = [
            YouTubeVideo(
                video_id=ytm_client.get_top_video_id(title),
                track=title,
                artist=artist,
                album="",
                playlist=playlist,
                comments="",
                thumbnail_url=ytm_client.get_thumbnail_url(title),
            )
            for title, artist in tqdm(songs, mininterval=5)
        ]
        playlist_map[playlist] = videos
    return playlist_map


def get_youtube_music_videos(playlists):
    playlist_map = {}
    for playlist, url in playlists.items():
        print(f"locating ytm video_ids for {playlist}...")
        py_playlist = Playlist(url)
        videos = [
            YouTubeVideo(
                video_id=video.video_id,
                track=info["title"],
                artist=info["artist"],
                album="",
                playlist=playlist,
                comments="",
                thumbnail_url=video.thumbnail_url,
            )
            for video in tqdm(py_playlist.videos, mininterval=5)
            if (info := get_song_title_artist(video.title))
        ]
        playlist_map[playlist] = videos
    return playlist_map
