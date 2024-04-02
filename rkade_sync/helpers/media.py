import typing as T
from dataclasses import dataclass
from functools import cached_property

import pydub.scipy_effects
import pydub.silence as silence
import utils
from pydub import AudioSegment
from pytube import Playlist, Stream, YouTube


@dataclass
class YTVideo:
    video_id: str
    track: str
    artist: str
    album: str
    playlist: str
    comments: str

    @property
    def tags(self):
        return {
            k: v
            for k, v in vars(self).items()
            if k in ["artist", "album", "playlist", "comments"]
        }

    @property
    def title(self):
        return f"{self.track} - {self.artist}"

    @property
    def fp(self):
        return f"{self.title}.mp3"

    @property
    def url(self):
        base = "https://music.youtube.com/watch?v"
        return f"{base}={self.video_id}"

    @property
    def duration(self):
        return self.youtube.length

    @cached_property
    def youtube(self) -> YouTube:
        return YouTube(url=self.url, use_oauth=True, allow_oauth_cache=True)

    def download_mp3(self, raw_directory, final_directory) -> str:
        raw_fp = self.download_stream(directory=raw_directory)
        return self.postprocess_audio(fp=raw_fp, directory=final_directory).name

    def postprocess_audio(self, fp, directory):
        song = AudioSegment.from_file(fp)[: self.duration * 1000]

        return song.export(
            f"{directory}/{self.fp}", format="mp3", bitrate="256k", tags=self.tags
        )

    def download_stream(self, directory) -> str:
        stream = self.get_best_stream()
        filename = f"{self.title}.{stream.subtype}"
        fp = stream.download(output_path=directory, filename=filename, max_retries=3)
        return fp

    def get_best_stream(self) -> Stream:
        return T.cast(
            Stream, self.youtube.streams.filter(only_audio=True).order_by("abr").last()
        )

    @staticmethod
    def guess_bpm(song: AudioSegment):
        song = song.low_pass_filter(120.0)  # type: ignore
        beat_loudness = T.cast(int, song.dBFS)

        # the fastest tempo we'll allow is 240 bpm (60000ms / 240beats)
        minimum_silence = int(60000 / 240.0)

        nonsilent_times = silence.detect_nonsilent(song, minimum_silence, beat_loudness)

        spaces_between_beats = []
        last_t = nonsilent_times[0][0]

        for peak_start, _ in nonsilent_times[1:]:
            spaces_between_beats.append(peak_start - last_t)
            last_t = peak_start

        # We'll base our guess on the median space between beats
        spaces_between_beats = sorted(spaces_between_beats)
        space = spaces_between_beats[len(spaces_between_beats) // 2]

        bpm = 60000 / space
        return bpm


def get_spotify_videos(sp_playlists, ytm_client) -> T.Dict[str, T.List[YTVideo]]:
    playlist_map = {}
    for playlist, songs in sp_playlists.items():
        print(f"finding for {playlist}...")
        videos = []
        total = len(songs)
        for i, song in enumerate(songs):
            if i % 10 == 0:
                print(f"{i}/{total}")
            title, artist = song
            track, album, video_id = ytm_client.return_top_video_match(title)
            video = YTVideo(
                video_id=video_id,
                track=track,
                artist=artist,
                album=album,
                playlist=playlist,
                comments="",
            )
            videos.append(video)
        playlist_map[playlist] = videos
    return playlist_map


def get_ytm_videos(playlists: T.Dict[str, str]) -> T.Dict[str, T.List[YTVideo]]:
    playlist_map = {}
    for playlist, url in playlists.items():
        videos = []
        for i, v in enumerate(Playlist(url).videos):
            if i % 10 == 0:
                print(i)
            video_info = utils.get_song_title_artist(v.title)
            video_id = v.video_id
            track = video_info["title"]
            artist = video_info["artist"]
            album = ""
            video = YTVideo(
                video_id=video_id,
                track=track,
                artist=artist,
                album=album,
                playlist=playlist,
                comments="",
            )
            videos.append(video)
        playlist_map[playlist] = videos
    return playlist_map
