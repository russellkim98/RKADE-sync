import itertools

from config import ROOT, SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_USER
from playlist_manager import PlaylistManager
from spotify import SpotifyClient


def get_spotify_playlists(spotify_client):
    return spotify_client.get_spotify_playlists_and_songs("rekordbox")


def main():

    playlist_manager = PlaylistManager(ROOT)
    youtube_info = playlist_manager.ytm_downloader.get_youtube_playlists()

    spotify_client = SpotifyClient(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET,
        user=SPOTIFY_USER,
    )
    spotify_info = get_spotify_playlists(spotify_client)

    playlists = {
        playlist: playlist_manager.standardize_playlist(
            playlist,
            list(
                itertools.chain(
                    spotify_info.get(playlist, {}), youtube_info.get(playlist, {})
                )
            ),
        )
        for playlist in itertools.chain(spotify_info.keys(), youtube_info.keys())
        # for playlist in ["rekordbox_techno"]
    }

    for name, info in playlists.items():
        playlist_manager.download_playlist(name, info)

    print("Done!")


if __name__ == "__main__":
    main()
