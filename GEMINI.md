# Gemini Project Context: RKADE-sync

This document provides a comprehensive overview of the `RKADE-sync` project for the Gemini AI assistant.

## 1. Project Overview

`RKADE-sync` is a Python-based command-line tool designed to synchronize a user's Spotify music library to a local directory. It achieves this by fetching track information from Spotify (liked songs and specified playlists) and then finding and downloading the corresponding audio from YouTube.

The core workflow is as follows:
1.  **Authentication**: Connects to Spotify and YouTube Music APIs.
2.  **Fetch Spotify Data**: Retrieves a list of tracks from the user's liked songs and playlists (specifically those containing "rekordbox_").
3.  **Find on YouTube**: For each Spotify track, it searches YouTube for potential matches.
4.  **AI-Powered Matching**: An Ollama client (using a model like Gemma) analyzes the YouTube search results against the original Spotify track data to find the best match based on title, artist, duration, and channel credibility.
5.  **Download**: Downloads the best-matched YouTube video as an MP3 file using `yt-dlp`.
6.  **Tagging**: Applies ID3 metadata (title, artist, album) to the downloaded MP3 file.
7.  **Caching**: Caches Spotify data and a log of downloaded YouTube video IDs to prevent redundant API calls and downloads on subsequent runs.

## 2. Project Structure

```
/
├── .env.example        # Example environment variables file
├── .gitignore          # Git ignore rules
├── poetry.lock         # Poetry lock file for deterministic builds
├── pyproject.toml      # Project metadata and dependencies (Poetry)
├── README.md           # Project documentation
├── music_downloads/    # Default directory for downloaded MP3s
│   └── downloaded_videos.json # Log of downloaded YouTube video IDs
├── src/                # Main source code directory
│   ├── main.py         # Main entry point, CLI argument parsing, and orchestration
│   ├── config.py       # Loads configuration from environment variables
│   ├── data_models.py  # Defines dataclasses for Track and YouTubeCandidate
│   ├── spotify_client.py # Manages Spotify API interaction and caching
│   ├── youtube_client.py # Manages YouTube Music API interaction and candidate scoring
│   ├── ollama_client.py  # Handles AI-based song similarity analysis
│   ├── download_manager.py # Manages file downloads, retries, and metadata tagging
│   └── logging_config.py # Configures application-wide logging
└── tests/              # (Currently empty) Directory for tests
```

## 3. Key Files & Logic

### `src/main.py`
-   **Orchestration**: The `MusicSyncOrchestrator` class coordinates the entire process.
-   **CLI Interface**: Uses `argparse` to handle command-line arguments (`--liked`, `--playlists`, `--all`).
-   **Concurrency**: Uses `asyncio` to process and download tracks concurrently, with a semaphore (`MAX_WORKERS`) to limit simultaneous downloads.
-   **Deduplication**: Removes duplicate tracks from the initial Spotify list before processing.

### `src/spotify_client.py`
-   **Authentication**: Uses `spotipy` with OAuth2 to connect to the Spotify API.
-   **Data Fetching**: Retrieves liked songs and tracks from playlists whose names contain `rekordbox_`.
-   **Caching**: Implements a simple JSON-based cache (`spotify_cache.json`) to store fetched track lists, reducing API calls.

### `src/youtube_client.py`
-   **Searching**: Uses `ytmusicapi` to search for tracks on YouTube. It performs multiple queries to find the best candidates.
-   **Candidate Scoring**: Implements a `_calculate_quality_score` method to rank search results based on a weighted system defined in `config.py` (e.g., official channels, duration match, view count).

### `src/ollama_client.py`
-   **AI Similarity**: Interacts with a local Ollama instance to provide advanced matching.
-   **Prompt Engineering**: Constructs a detailed prompt (`_build_similarity_prompt`) asking the LLM to rate YouTube candidates against a Spotify track.
-   **Fallback Logic**: If the Ollama service is unavailable or fails, it uses a simpler, non-AI string-matching algorithm (`_fallback_similarity`) to score candidates.

### `src/download_manager.py`
-   **Downloading**: Uses `yt-dlp` to download the audio from a given YouTube URL.
-   **Metadata**: Uses `eyed3` to write ID3 tags (title, artist, album) to the final MP3 file.
-   **Download Log**: Maintains a `downloaded_videos.json` file to ensure videos are not downloaded more than once.
-   **Retry Logic**: Implements an asynchronous retry mechanism for failed downloads.

### `src/config.py`
-   Loads all necessary credentials and settings from a `.env` file using `python-dotenv`.
-   Defines key parameters like download directory, concurrency limits, AI similarity thresholds, and quality scoring weights.

## 4. Dependencies & Setup

-   **Dependency Management**: The project uses [Poetry](https://python-poetry.org/) for managing dependencies.
-   **Core Dependencies**: `spotipy`, `ytmusicapi`, `yt-dlp`, `eyed3`, `httpx` (for Ollama), `python-dotenv`.
-   **Setup**:
    1.  Install dependencies: `poetry install`
    2.  Configure environment: Copy `.env.example` to `.env` and fill in the API credentials for Spotify and optionally YouTube Music and Ollama.
    3.  Run: `python -m src.main --all`

