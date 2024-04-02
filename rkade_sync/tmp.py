# run.py

import multiprocessing
import subprocess
from pathlib import Path

from client.spotify import SpotifyClient
from client.youtube_music import YouTubeMusicClient
from config import ROOT_DIR, SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_USER, YT_PLAYLISTS
from helpers import media_helpers, utils

RAW_DIR = ROOT_DIR / 'raw'


def initialize_clients():
    spotify_client = SpotifyClient(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET,
        user=SPOTIFY_USER,
    )
    youtube_music_client = YouTubeMusicClient(auth='oauth.json')
    return spotify_client, youtube_music_client


def download_song(yt_video, playlist):
    final_directory = ROOT_DIR / 'playlists' / playlist
    file_path = yt_video.download_mp3(
        raw_directory=RAW_DIR, final_directory=final_directory
    )
    utils.set_thumbnail(file_path, yt_video.thumbnail_url)


def main():
    subprocess.run(['ytmusicapi', 'oauth'])
    spotify_client, youtube_music_client = initialize_clients()
    spotify_videos = media_helpers.get_spotify_videos(spotify_client.get_spotify_playlists_and_songs('rekordbox'), youtube_music_client)
    youtube_videos = media_helpers.get_youtube_music_videos(YT_PLAYLISTS)
    return {**spotify_videos, **youtube_videos}


if __name__ == '__main__':
    tracks = main()
    with multiprocessing.Pool() as pool:
        pool.starmap(download_song, [(video, playlist) for playlist, videos in tracks.items() for video in videos])

# helpers/media_helpers.py

from dataclasses import dataclass
from pathlib import Path
from pytube import YouTube

from utils import get_song_title_artist


@dataclass
class YouTubeVideo:
    video_id: str
    track: str
    artist: str
    album: str
    playlist: str
    comments: str
    thumbnail_url: str

    def download_mp3(self, raw_directory, final_directory) -> Path:
        youtube = YouTube(f'https://music.youtube.com/watch?v={self.video_id}')
        stream = youtube.streams.filter(only_audio=True).order_by("abr").last()
        raw_file_path = stream.download(output_path=raw_directory, filename=f"{self.track}.{stream.subtype}")
        final_file_path = final_directory / f"{self.track}.mp3"
        raw_audio = AudioSegment.from_file(raw_file_path)
        raw_audio.export(final_file_path, format="mp3", bitrate="256k", tags={
            "artist": self.artist,
            "album": self.album,
            "playlist": self.playlist,
            "comments": self.comments,
        })
        return final_file_path


def get_spotify_videos(sp_playlists, ytm_client):
    playlist_map = {}
    for playlist, songs in sp_playlists.items():
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
            for title, artist in songs
        ]
        playlist_map[playlist] = videos
    return playlist_map


def get_youtube_music_videos(playlists):
    playlist_map = {}
    for playlist, url in playlists.items():
        py_playlist = Playlist(url)
        videos = [
            YouTubeVideo(
                video_id=video.video_id,
                track=info['title'],
                artist=info['artist'],
                album="",
                playlist=playlist,
                comments="",
                thumbnail_url=video.thumbnail_url,
            )
            for video in py_playlist.videos if (info := get_song_title_artist(video.title))
        ]
        playlist_map[playlist] = videos
    return playlist_map

# client/spotify.py

from spotipy import Spotify
from spotipy.oauth2 import SpotifyClientCredentials


class SpotifyClient(Spotify):
    def __init__(self, client_id, client_secret, user):
        super().__init__(auth_manager=SpotifyClientCredentials(client_id=client_id, client_secret=client_secret))
        self.user = user

    def get_spotify_playlists_and_songs(self, fuzzy_name):
        playlists = self.user_playlists(self.user)
        matched_playlists = {pl['name']: pl['id'] for pl in playlists['items'] if fuzzy_name in pl['name']}
        songs = {
            name: [
                (track['track']['name'], track['track']['artists'][0]['name'])
                for track in self.playlist_items(pl_id, fields="items(track(name,artists(name)))")['items']
            ]
            for name, pl_id in matched_playlists.items()
        }
        return songs

# client/youtube_music.py

from ytmusicapi import YTMusic


class YouTubeMusicClient(YTMusic):
    def get_top_video_id(self, song_name):
        results = self.search(query=song_name, filter="songs")
        return results[0]['videoId'] if results else None

    def get_thumbnail_url(self, song_name):
        results = self.search(query=song_name, filter="songs")
        return results[0]['thumbnails'][-1]['url'] if results else None

# helpers/utils.py

import eyed3
import requests
from eyed3.id3.frames import ImageFrame

def set_thumbnail(mp3_file, image_url):
    response = requests.get(image_url)
    if response.status_code == 200:
        audiofile = eyed3.load(mp3_file)
        if audiofile.tag is None:
            audiofile.initTag()
        audiofile.tag.images.set(ImageFrame.FRONT_COVER, response.content, 'image/jpeg')
        audiofile.tag.save()