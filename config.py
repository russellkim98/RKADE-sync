"""Configuration settings for the music matcher application."""


class Config:
    """Configuration for the music matcher system."""

    # Matching thresholds
    LLM_SCORE_THRESHOLD = 85
    LLM_SCORE_DIFFERENCE = 15

    # Matcher weights
    TITLE_WEIGHT = 0.5
    ARTIST_WEIGHT = 0.3
    DURATION_WEIGHT = 0.2

    # API limits
    MAX_YOUTUBE_RESULTS = 10
    SPOTIFY_BATCH_SIZE = 100

    # LLM settings
    LLM_MODEL = "gemma3:12b"
    LLM_TEMPERATURE = 0.3
    LLM_CONTEXT_SIZE = 4096

    # Database settings
    DATABASE_PATH = "music_matcher.db"

    # Logging
    LOG_LEVEL = "INFO"
    LOG_FILE = "music_matcher.log"
