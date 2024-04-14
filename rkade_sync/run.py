import hashlib
import itertools
import time

import browser_cookie3
from config import (
    ROOT,
    SPOTIFY_CLIENT_ID,
    SPOTIFY_CLIENT_SECRET,
    SPOTIFY_USER,
    YOUTUBE_MUSIC_COOKIE_NAMES,
    YOUTUBE_MUSIC_HEADERS,
)
from playlist_manager import PlaylistManager
from spotify import SpotifyClient
from youtube import YouTubeMusicDownloader


def get_youtube_cookies(cookie_jar, cookie_names):
    return {c.name: c.value for c in cookie_jar if c.name in cookie_names}


def get_youtube_playlists(ytm_downloader):
    all_playlists = ytm_downloader.client.get_library_playlists()
    return {
        playlist["title"]: ytm_downloader.client.get_playlist(
            playlist["playlistId"], limit=400
        )["tracks"]
        for playlist in all_playlists
        if "rekordbox" in playlist["title"]
    }


def get_spotify_playlists(spotify_client):
    return spotify_client.get_spotify_playlists_and_songs("rekordbox")


def generate_sapisidhash_header(SAPISID, origin="https://www.youtube.com"):
    time_now = round(time.time())
    sapisidhash = hashlib.sha1(f"{time_now} {SAPISID} {origin}".encode()).hexdigest()
    return f"SAPISIDHASH {time_now}_{sapisidhash}"


def main():
    cookie_jar = browser_cookie3.chrome()
    cookies_youtube_music = get_youtube_cookies(cookie_jar, YOUTUBE_MUSIC_COOKIE_NAMES)
    YOUTUBE_MUSIC_HEADERS["authorization"] = generate_sapisidhash_header(
        cookies_youtube_music["SAPISID"]
    )
    YOUTUBE_MUSIC_HEADERS["cookie"] = "; ".join(
        [f"{k}={v}" for k, v in cookies_youtube_music.items()]
    )

    ytm_downloader = YouTubeMusicDownloader(headers=YOUTUBE_MUSIC_HEADERS)
    youtube_info = get_youtube_playlists(ytm_downloader)

    spotify_client = SpotifyClient(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET,
        user=SPOTIFY_USER,
    )
    spotify_info = get_spotify_playlists(spotify_client)

    playlist_manager = PlaylistManager(ytm_downloader, ROOT)

    playlists = {
        playlist: playlist_manager.standardize_playlist(
            playlist,
            list(
                itertools.chain(
                    spotify_info.get(playlist, {}), youtube_info.get(playlist, {})
                )
            ),
        )
        # for playlist in itertools.chain(spotify_info.keys(), youtube_info.keys())
        for playlist in ["rekordbox_house_pop"]
    }

    for name, info in playlists.items():
        playlist_manager.download_playlist(name, info)


if __name__ == "__main__":
    main()
