# Spotify Downloader #

## Requirements ##

- [ffmpeg](https://ffmpeg.org/)
- [poetry](https://python-poetry.org/)
- [ytdlp](https://github.com/yt-dlp/yt-dlp)

## Usage ##

First, fill out the `config.py` file with the following information:

```python
# Where you want your music to go
ROOT_DIR = ""

# Spotify Credentials
SPOTIPY_CLIENT_ID = ""
SPOTIPY_CLIENT_SECRET = ""

# Dict of Playlists from youtube (optional)
YT_PLAYLISTS = {
}

# Youtube Music OAUTH json
YTMUSIC_OAUTH_DIR = ""

# Spotify Username
USER = "russellkim98"

```

```bash
poetry install
poetry shell
poetry run python spotify_downloader.py
```
