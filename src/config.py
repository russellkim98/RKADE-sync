"""Configuration loader for the application."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Spotify API credentials
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
SPOTIFY_REDIRECT_URI = os.getenv("SPOTIFY_REDIRECT_URI")

# YouTube Music auth token (JSON string)
YTMUSIC_AUTH_TOKEN = os.getenv("YTMUSIC_AUTH_TOKEN")

# Ollama configuration
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma:latest")

# Download settings
DOWNLOAD_DIR = Path(os.getenv("DOWNLOAD_DIR", "./music_downloads"))
MAX_WORKERS = int(os.getenv("MAX_WORKERS", "4"))
SIMILARITY_THRESHOLD = float(os.getenv("SIMILARITY_THRESHOLD", "0.7"))
MAX_YT_CANDIDATES = int(os.getenv("MAX_YT_CANDIDATES", "5"))
RETRY_ATTEMPTS = int(os.getenv("RETRY_ATTEMPTS", "3"))

# Quality preferences
QUALITY_WEIGHTS = {
    "official_artist": 100,
    "youtube_music": 90,
    "verified_channel": 80,
    "topic_channel": 70,
    "high_views": 30,
    "recent_upload": 20,
    "exact_duration": 50,
    "audio_quality": 40,
}

# Create download directory
DOWNLOAD_DIR.mkdir(exist_ok=True)
