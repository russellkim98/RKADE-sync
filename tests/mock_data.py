
from src.data_models import Track, YouTubeCandidate

# Mock Spotify Track
mock_spotify_track = Track(
    name="Test Song",
    artist="Test Artist",
    album="Test Album",
    duration_ms=180000,
    spotify_id="test_spotify_id",
    source="spotify_liked",
    popularity=80,
    release_date="2023-01-01",
)

# Mock YouTube Candidates
mock_youtube_candidates = [
    YouTubeCandidate(
        video_id="test_video_id_1",
        title="Test Artist - Test Song (Official Video)",
        artist="Test Artist",
        duration_seconds=182,
        view_count=1000000,
        channel_name="Test Artist VEVO",
        is_official=True,
        is_music=True,
        quality_score=95.0,
    ),
    YouTubeCandidate(
        video_id="test_video_id_2",
        title="Test Song - Test Artist (Lyrics)",
        artist="Test Artist",
        duration_seconds=180,
        view_count=500000,
        channel_name="Random Uploader",
        is_official=False,
        is_music=True,
        quality_score=70.0,
    ),
]

# Mock Ollama AI Response
mock_ollama_response = """
Candidate 1: 0.9 - Perfect match, official video.
Candidate 2: 0.7 - Good match, but not official.
"""
