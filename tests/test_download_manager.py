
import unittest
import asyncio
from unittest.mock import patch, MagicMock, mock_open
from src.download_manager import DownloadManager
from tests.mock_data import mock_spotify_track, mock_youtube_candidates

class TestDownloadManager(unittest.TestCase):

    @patch('pathlib.Path.exists', return_value=True)
    @patch('builtins.open', new_callable=mock_open, read_data='{"downloaded_ids": ["test_video_id_2"]}')
    def test_load_download_log(self, mock_file, mock_exists):
        """Test loading the download log."""
        manager = DownloadManager()
        self.assertIn("test_video_id_2", manager.download_log["downloaded_ids"])

    @patch('src.download_manager.yt_dlp.YoutubeDL')
    @patch('src.download_manager.eyed3.load')
    @patch('builtins.open', new_callable=mock_open)
    def test_download_track_success(self, mock_file, mock_eyed3, mock_ytdl):
        """Test successful track download."""
        mock_ytdl_instance = MagicMock()
        mock_ytdl.return_value.__enter__.return_value = mock_ytdl_instance

        manager = DownloadManager()
        async def run_test():
            result = await manager.download_track(mock_spotify_track, mock_youtube_candidates[0])
            self.assertTrue(result)
            mock_ytdl_instance.download.assert_called_once()
            mock_eyed3.assert_called_once()

        asyncio.run(run_test())

    @patch('src.download_manager.yt_dlp.YoutubeDL', side_effect=Exception("Download error"))
    def test_download_track_failure(self, mock_ytdl):
        """Test failed track download."""
        manager = DownloadManager()
        async def run_test():
            result = await manager.download_track(mock_spotify_track, mock_youtube_candidates[0])
            self.assertFalse(result)

        asyncio.run(run_test())

    def test_is_downloaded(self):
        """Test checking if a track is already downloaded."""
        manager = DownloadManager()
        manager.download_log = {"downloaded_ids": ["test_video_id_1"]}
        self.assertTrue(manager.is_downloaded("test_video_id_1"))
        self.assertFalse(manager.is_downloaded("test_video_id_2"))

if __name__ == '__main__':
    unittest.main()
