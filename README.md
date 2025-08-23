# RKADE-sync

This project is a music synchronization tool that syncs your Spotify library to a local directory by downloading the tracks from YouTube.

## Features

- **Spotify Integration**: Fetches liked songs and playlists from your Spotify account.
- **YouTube Music Search**: Searches for the corresponding tracks on YouTube Music.
- **AI-Powered Matching**: Uses Ollama with a Gemma model to intelligently match songs between Spotify and YouTube.
- **Asynchronous Downloads**: Downloads multiple tracks concurrently.
- **Caching**: Caches Spotify data and downloaded video IDs to avoid redundant operations.
- **Metadata**: Adds ID3 tags to the downloaded files.

## Setup

1.  **Clone the repository:**

    ```bash
    git clone <repository-url>
    cd RKADE-sync
    ```

2.  **Install dependencies:**

    ```bash
    poetry install
    ```

3.  **Set up environment variables:**

    Create a `.env` file in the root of the project by copying the `.env.example` file:

    ```bash
    cp .env.example .env
    ```

    Then, fill in the required values in the `.env` file.

4.  **Run the application:**

    ```bash
    python -m src.main --all
    ```

## Usage

```
usage: main.py [-h] [--liked] [--playlists] [--all] [--log-level {DEBUG,INFO,WARNING,ERROR}]

Sync your Spotify music to a local library.

options:
  -h, --help            show this help message and exit
  --liked               Sync liked songs.
  --playlists           Sync songs from playlists.
  --all                 Sync both liked songs and playlists.
  --log-level {DEBUG,INFO,WARNING,ERROR}
                        Set the logging level.
```
