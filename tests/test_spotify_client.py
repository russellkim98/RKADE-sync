
import unittest
from unittest.mock import patch, MagicMock
from src.spotify_client import SpotifyManager
from tests.mock_data import mock_spotify_track

class TestSpotifyManager(unittest.TestCase):

    @patch('src.spotify_client.spotipy.Spotify')
    def test_authenticate_success(self, mock_spotify_class):
        """Test successful Spotify authentication."""
        mock_client = MagicMock()
        mock_client.current_user.return_value = {'display_name': 'Test User'}
        mock_spotify_class.return_value = mock_client

        manager = SpotifyManager()
        self.assertTrue(manager.authenticate())
        self.assertEqual(manager.client, mock_client)

    @patch('src.spotify_client.spotipy.Spotify', side_effect=Exception("Auth error"))
    def test_authenticate_failure(self, mock_spotify_class):
        """Test failed Spotify authentication."""
        manager = SpotifyManager()
        self.assertFalse(manager.authenticate())

    @patch('src.spotify_client.spotipy.Spotify')
    def test_get_liked_songs(self, mock_spotify_class):
        """Test fetching liked songs."""
        mock_client = MagicMock()
        mock_client.current_user_saved_tracks.return_value = {
            'items': [{
                'track': {
                    'name': mock_spotify_track.name,
                    'artists': [{'name': mock_spotify_track.artist}],
                    'album': {'name': mock_spotify_track.album, 'release_date': mock_spotify_track.release_date},
                    'duration_ms': mock_spotify_track.duration_ms,
                    'id': mock_spotify_track.spotify_id,
                    'popularity': mock_spotify_track.popularity,
                }
            }],
            'next': None
        }
        mock_spotify_class.return_value = mock_client

        manager = SpotifyManager()
        manager.client = mock_client
        tracks = manager.get_liked_songs()

        self.assertEqual(len(tracks), 1)
        self.assertEqual(tracks[0].name, mock_spotify_track.name)

if __name__ == '__main__':
    unittest.main()
