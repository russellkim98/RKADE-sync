import unittest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from src.ollama_client import OllamaClient
from tests.mock_data import mock_spotify_track, mock_youtube_candidates, mock_ollama_response

class TestOllamaClient(unittest.TestCase):

    @patch('src.ollama_client.httpx.AsyncClient')
    def test_is_available_success(self, mock_async_client):
        """Test when Ollama service is available."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_async_client.return_value.get = AsyncMock(return_value=mock_response)

        client = OllamaClient()
        async def run_test():
            self.assertTrue(await client.is_available())

        asyncio.run(run_test())

    @patch('src.ollama_client.httpx.AsyncClient')
    def test_is_available_failure(self, mock_async_client):
        """Test when Ollama service is unavailable."""
        mock_async_client.return_value.get.side_effect = Exception("Connection error")

        client = OllamaClient()
        async def run_test():
            self.assertFalse(await client.is_available())

        asyncio.run(run_test())

    @patch('src.ollama_client.httpx.AsyncClient')
    def test_analyze_song_similarity_ai_success(self, mock_async_client):
        """Test song similarity analysis with successful AI response."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {'response': mock_ollama_response}
        mock_async_client.return_value.post = AsyncMock(return_value=mock_response)
        mock_async_client.return_value.get = AsyncMock(return_value=mock_response)

        client = OllamaClient()
        async def run_test():
            scores = await client.analyze_song_similarity(mock_spotify_track, mock_youtube_candidates)
            self.assertEqual(len(scores), 2)
            self.assertEqual(scores[0][1], 0.9)

        asyncio.run(run_test())

    @patch('src.ollama_client.httpx.AsyncClient')
    def test_analyze_song_similarity_ai_failure_fallback(self, mock_async_client):
        """Test fallback mechanism when AI analysis fails."""
        mock_async_client.return_value.post.side_effect = Exception("AI error")
        mock_async_client.return_value.get = AsyncMock(return_value=MagicMock()) # To avoid is_available error

        client = OllamaClient()
        async def run_test():
            scores = await client.analyze_song_similarity(mock_spotify_track, mock_youtube_candidates)
            self.assertTrue(len(scores) > 0)

        asyncio.run(run_test())

if __name__ == '__main__':
    unittest.main()