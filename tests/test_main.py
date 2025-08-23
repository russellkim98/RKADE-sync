
import unittest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from src.main import MusicSyncOrchestrator
from tests.mock_data import mock_spotify_track, mock_youtube_candidates

class TestMusicSyncOrchestrator(unittest.TestCase):

    @patch('src.main.SpotifyManager')
    @patch('src.main.YouTubeMusicManager')
    @patch('src.main.OllamaClient')
    @patch('src.main.DownloadManager')
    def test_sync_music_library_liked_songs(self, mock_download_manager, mock_ollama_client, mock_ytmusic_manager, mock_spotify_manager):
        """Test syncing liked songs."""
        # Mock SpotifyManager
        mock_spotify_manager.return_value.authenticate.return_value = True
        mock_spotify_manager.return_value.get_liked_songs.return_value = [mock_spotify_track]
        mock_spotify_manager.return_value.get_all_playlists.return_value = []

        # Mock YouTubeMusicManager
        mock_ytmusic_manager.return_value.authenticate.return_value = True
        mock_ytmusic_manager.return_value.search_candidates = AsyncMock(return_value=mock_youtube_candidates)

        # Mock OllamaClient
        mock_ollama_client.return_value.is_available = AsyncMock(return_value=True)
        mock_ollama_client.return_value.analyze_song_similarity = AsyncMock(return_value=[(mock_youtube_candidates[0], 0.9)])

        # Mock DownloadManager
        mock_download_manager.return_value.download_track = AsyncMock(return_value=True)

        orchestrator = MusicSyncOrchestrator()
        async def run_test():
            await orchestrator.sync_music_library(include_liked=True, include_playlists=False)
            mock_spotify_manager.return_value.get_liked_songs.assert_called_once()
            mock_ytmusic_manager.return_value.search_candidates.assert_called_once()
            mock_ollama_client.return_value.analyze_song_similarity.assert_called_once()
            mock_download_manager.return_value.download_track.assert_called_once()

        asyncio.run(run_test())

if __name__ == '__main__':
    unittest.main()
