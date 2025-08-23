
import unittest
import asyncio
from unittest.mock import patch, MagicMock
from src.youtube_client import YouTubeMusicManager
from tests.mock_data import mock_spotify_track, mock_youtube_candidates

class TestYouTubeMusicManager(unittest.TestCase):

    @patch('src.youtube_client.YTMusic')
    def test_authenticate_success(self, mock_ytmusic_class):
        """Test successful YouTube Music authentication."""
        mock_client = MagicMock()
        mock_ytmusic_class.return_value = mock_client

        manager = YouTubeMusicManager()
        self.assertTrue(manager.authenticate())
        self.assertEqual(manager.client, mock_client)

    @patch('src.youtube_client.YTMusic', side_effect=Exception("Auth error"))
    def test_authenticate_failure(self, mock_ytmusic_class):
        """Test failed YouTube Music authentication."""
        manager = YouTubeMusicManager()
        self.assertFalse(manager.authenticate())

    @patch('src.youtube_client.YTMusic')
    def test_search_candidates(self, mock_ytmusic_class):
        """Test searching for YouTube candidates."""
        mock_client = MagicMock()
        mock_client.search.return_value = [
            {
                'videoId': candidate.video_id,
                'title': candidate.title,
                'artists': [{'name': candidate.artist}],
                'duration': f'{candidate.duration_seconds // 60}:{candidate.duration_seconds % 60:02d}',
                'views': f'{candidate.view_count:,}',
                'channel': {'name': candidate.channel_name},
            }
            for candidate in mock_youtube_candidates
        ]
        mock_ytmusic_class.return_value = mock_client

        manager = YouTubeMusicManager()
        manager.client = mock_client

        async def run_test():
            candidates = await manager.search_candidates(mock_spotify_track)
            self.assertEqual(len(candidates), 2)
            self.assertEqual(candidates[0].video_id, mock_youtube_candidates[0].video_id)

        asyncio.run(run_test())

if __name__ == '__main__':
    unittest.main()
