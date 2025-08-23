"""Data models for the application."""

from dataclasses import dataclass, asdict


@dataclass
class Track:
    name: str
    artist: str
    album: str = ""
    duration_ms: int = 0
    spotify_id: str = ""
    youtube_id: str = ""
    source: str = ""
    popularity: int = 0
    release_date: str = ""

    def __str__(self):
        return f"{self.artist} - {self.name}"

    def to_dict(self):
        return asdict(self)


@dataclass
class YouTubeCandidate:
    video_id: str
    title: str
    artist: str
    duration_seconds: int
    view_count: int
    channel_name: str
    is_official: bool
    is_music: bool
    quality_score: float
    upload_date: str = ""

    def __str__(self):
        return f"{self.title} by {self.artist} ({self.channel_name})"
