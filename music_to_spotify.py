# %% [markdown]
# # Music Library Sync with AI-Powered Matching
# 
# This notebook syncs Spotify and YouTube Music libraries using Ollama/Gemma for intelligent song matching
# and prioritizes official, high-quality uploads.

# %% [markdown]
# ## 1. Configuration and Imports

# %%
import os
import json
import time
import logging
import requests
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd

# Music APIs
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from ytmusicapi import YTMusic
import yt_dlp

# Audio processing
import eyed3

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('music_sync.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# %% [markdown]
# ## 2. Configuration Variables (Update these with your values)

# %%
# === CONFIGURATION SECTION - UPDATE THESE ===

# Spotify API credentials
SPOTIFY_CLIENT_ID = "your_spotify_client_id_here"
SPOTIFY_CLIENT_SECRET = "your_spotify_client_secret_here"
SPOTIFY_REDIRECT_URI = "http://localhost:8888/callback"

# YouTube Music auth file (optional - leave empty string if not using)
YTMUSIC_AUTH_FILE = ""  # Path to headers_auth.json or leave empty

# Ollama configuration
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "gemma:latest"

# Download settings
DOWNLOAD_DIR = Path("./music_downloads")
MAX_WORKERS = 2  # Number of concurrent downloads
SIMILARITY_THRESHOLD = 0.7  # AI similarity threshold (0.0-1.0)
MAX_YT_CANDIDATES = 5  # Number of YouTube candidates to analyze per song
RETRY_ATTEMPTS = 3

# Quality preferences (higher number = higher preference)
QUALITY_WEIGHTS = {
    'official_artist': 100,     # Official artist channel
    'youtube_music': 90,        # YouTube Music official
    'verified_channel': 80,     # Verified channel
    'topic_channel': 70,        # Auto-generated topic channels
    'high_views': 30,           # High view count
    'recent_upload': 20,        # Recently uploaded
    'exact_duration': 50,       # Duration matches Spotify
    'audio_quality': 40         # Audio quality indicators
}

# Create download directory
DOWNLOAD_DIR.mkdir(exist_ok=True)

print("Configuration loaded successfully!")

# %% [markdown]
# ## 3. Data Classes and Utility Functions

# %%
@dataclass
class Track:
    name: str
    artist: str
    album: str = ""
    duration_ms: int = 0
    spotify_id: str = ""
    youtube_id: str = ""
    source: str = ""
    popularity: int = 0
    release_date: str = ""
    
    def __str__(self):
        return f"{self.artist} - {self.name}"
    
    def to_dict(self):
        return {
            'name': self.name,
            'artist': self.artist,
            'album': self.album,
            'duration_ms': self.duration_ms,
            'spotify_id': self.spotify_id,
            'youtube_id': self.youtube_id,
            'source': self.source,
            'popularity': self.popularity,
            'release_date': self.release_date
        }

@dataclass
class YouTubeCandidate:
    video_id: str
    title: str
    artist: str
    duration_seconds: int
    view_count: int
    channel_name: str
    is_official: bool
    is_music: bool
    quality_score: float
    upload_date: str = ""
    
    def __str__(self):
        return f"{self.title} by {self.artist} ({self.channel_name})"

def safe_filename(text: str) -> str:
    """Create a safe filename from text"""
    return "".join(c for c in text if c.isalnum() or c in (' ', '-', '_', '.')).strip()

def format_duration(ms: int) -> str:
    """Convert milliseconds to MM:SS format"""
    seconds = ms // 1000
    minutes = seconds // 60
    seconds = seconds % 60
    return f"{minutes}:{seconds:02d}"

print("Data classes and utilities defined!")

# %% [markdown]
# ## 4. Ollama Integration for AI-Powered Song Matching

# %%
class OllamaClient:
    def __init__(self, base_url: str = OLLAMA_BASE_URL, model: str = OLLAMA_MODEL):
        self.base_url = base_url
        self.model = model
        self.session = requests.Session()
    
    def is_available(self) -> bool:
        """Check if Ollama is available"""
        try:
            response = self.session.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def generate(self, prompt: str, temperature: float = 0.1) -> str:
        """Generate response using Ollama"""
        try:
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "top_p": 0.9,
                    "top_k": 40
                }
            }
            
            response = self.session.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                return response.json().get('response', '').strip()
            else:
                logger.error(f"Ollama API error: {response.status_code}")
                return ""
        except Exception as e:
            logger.error(f"Ollama request failed: {e}")
            return ""
    
    def analyze_song_similarity(self, spotify_track: Track, youtube_candidates: List[YouTubeCandidate]) -> List[Tuple[YouTubeCandidate, float]]:
        """Use AI to analyze similarity between Spotify track and YouTube candidates"""
        
        prompt = f"""You are a music expert analyzing song matches. Compare this Spotify track with YouTube candidates and rate similarity.

Spotify Track:
- Title: "{spotify_track.name}"
- Artist: "{spotify_track.artist}"
- Album: "{spotify_track.album}"
- Duration: {format_duration(spotify_track.duration_ms)}

YouTube Candidates:
"""
        
        for i, candidate in enumerate(youtube_candidates, 1):
            duration_str = f"{candidate.duration_seconds // 60}:{candidate.duration_seconds % 60:02d}"
            prompt += f"""
{i}. Title: "{candidate.title}"
   Artist: "{candidate.artist}"
   Channel: "{candidate.channel_name}"
   Duration: {duration_str}
   Views: {candidate.view_count:,}
   Official: {candidate.is_official}
"""
        
        prompt += """
For each candidate, provide a similarity score from 0.0 to 1.0 based on:
- Title match (exact vs variations)
- Artist match (including features, collaborations)
- Duration similarity
- Channel credibility (official artists, verified channels)
- Audio quality indicators

Respond in this exact format for each candidate:
Candidate 1: 0.X - [brief reason]
Candidate 2: 0.X - [brief reason]
...

Be strict with scoring. Only give 0.9+ for near-perfect matches."""
        
        response = self.generate(prompt)
        
        # Parse the response
        similarity_scores = []
        lines = [line.strip() for line in response.split('\n') if line.strip()]
        
        for line in lines:
            if line.startswith('Candidate'):
                try:
                    parts = line.split(':')
                    if len(parts) >= 2:
                        candidate_num = int(parts[0].split()[-1]) - 1
                        score_part = parts[1].strip().split()[0]
                        score = float(score_part)
                        
                        if 0 <= candidate_num < len(youtube_candidates):
                            similarity_scores.append((youtube_candidates[candidate_num], score))
                except (ValueError, IndexError) as e:
                    logger.warning(f"Failed to parse similarity line: {line} - {e}")
                    continue
        
        # If parsing failed, fall back to basic matching
        if not similarity_scores:
            logger.warning("AI parsing failed, using fallback similarity")
            for candidate in youtube_candidates:
                score = self._fallback_similarity(spotify_track, candidate)
                similarity_scores.append((candidate, score))
        
        # Sort by similarity score (descending)
        similarity_scores.sort(key=lambda x: x[1], reverse=True)
        return similarity_scores
    
    def _fallback_similarity(self, spotify_track: Track, youtube_candidate: YouTubeCandidate) -> float:
        """Fallback similarity calculation if AI fails"""
        score = 0.0
        
        # Title similarity (basic)
        spotify_title = spotify_track.name.lower()
        youtube_title = youtube_candidate.title.lower()
        
        if spotify_title in youtube_title or youtube_title in spotify_title:
            score += 0.4
        elif any(word in youtube_title for word in spotify_title.split() if len(word) > 3):
            score += 0.2
        
        # Artist similarity
        spotify_artist = spotify_track.artist.lower()
        youtube_artist = youtube_candidate.artist.lower()
        
        if spotify_artist in youtube_artist or youtube_artist in spotify_artist:
            score += 0.3
        
        # Duration similarity
        if spotify_track.duration_ms > 0:
            spotify_seconds = spotify_track.duration_ms // 1000
            duration_diff = abs(spotify_seconds - youtube_candidate.duration_seconds)
            if duration_diff <= 5:
                score += 0.2
            elif duration_diff <= 15:
                score += 0.1
        
        # Official channel bonus
        if youtube_candidate.is_official:
            score += 0.1
        
        return min(score, 1.0)

# Initialize Ollama client
ollama = OllamaClient()

if ollama.is_available():
    print("✅ Ollama is available and ready!")
else:
    print("⚠️ Ollama is not available. Using fallback similarity matching.")

# %% [markdown]
# ## 5. Spotify Integration

# %%
class SpotifyManager:
    def __init__(self):
        self.client = None
        self.tracks = []
        
    def authenticate(self):
        """Authenticate with Spotify"""
        try:
            self.client = spotipy.Spotify(auth_manager=SpotifyOAuth(
                client_id=SPOTIFY_CLIENT_ID,
                client_secret=SPOTIFY_CLIENT_SECRET,
                redirect_uri=SPOTIFY_REDIRECT_URI,
                scope="user-library-read playlist-read-private playlist-read-collaborative"
            ))
            
            # Test the connection
            user = self.client.current_user()
            logger.info(f"✅ Connected to Spotify as: {user['display_name']}")
            return True
        except Exception as e:
            logger.error(f"❌ Spotify authentication failed: {e}")
            return False
    
    def get_liked_songs(self) -> List[Track]:
        """Get all liked songs from Spotify"""
        tracks = []
        
        try:
            logger.info("Fetching liked songs from Spotify...")
            results = self.client.current_user_saved_tracks(limit=50)
            
            while results:
                for item in results['items']:
                    track_data = item['track']
                    track = Track(
                        name=track_data['name'],
                        artist=', '.join([artist['name'] for artist in track_data['artists']]),
                        album=track_data['album']['name'],
                        duration_ms=track_data['duration_ms'],
                        spotify_id=track_data['id'],
                        source='spotify_liked',
                        popularity=track_data['popularity'],
                        release_date=track_data['album']['release_date']
                    )
                    tracks.append(track)
                
                if results['next']:
                    results = self.client.next(results)
                else:
                    break
            
            logger.info(f"✅ Found {len(tracks)} liked songs on Spotify")
            
        except Exception as e:
            logger.error(f"❌ Error fetching Spotify liked songs: {e}")
        
        return tracks
    
    def get_playlist_tracks(self, playlist_id: str, playlist_name: str) -> List[Track]:
        """Get tracks from a specific playlist"""
        tracks = []
        
        try:
            logger.info(f"Fetching playlist: {playlist_name}")
            results = self.client.playlist_tracks(playlist_id)
            
            while results:
                for item in results['items']:
                    if item['track'] and item['track']['id']:  # Skip local files
                        track_data = item['track']
                        track = Track(
                            name=track_data['name'],
                            artist=', '.join([artist['name'] for artist in track_data['artists']]),
                            album=track_data['album']['name'],
                            duration_ms=track_data['duration_ms'],
                            spotify_id=track_data['id'],
                            source=f'spotify_playlist_{playlist_name}',
                            popularity=track_data['popularity'],
                            release_date=track_data['album']['release_date']
                        )
                        tracks.append(track)
                
                if results['next']:
                    results = self.client.next(results)
                else:
                    break
            
            logger.info(f"✅ Found {len(tracks)} tracks in playlist: {playlist_name}")
            
        except Exception as e:
            logger.error(f"❌ Error fetching playlist {playlist_name}: {e}")
        
        return tracks
    
    def get_all_playlists(self) -> List[Track]:
        """Get tracks from all user playlists"""
        all_tracks = []
        
        try:
            playlists = self.client.current_user_playlists()
            user_id = self.client.current_user()['id']
            
            for playlist in playlists['items']:
                if playlist['owner']['id'] == user_id:  # Only user's own playlists
                    tracks = self.get_playlist_tracks(playlist['id'], playlist['name'])
                    all_tracks.extend(tracks)
        
        except Exception as e:
            logger.error(f"❌ Error fetching playlists: {e}")
        
        return all_tracks

# Initialize Spotify
spotify_manager = SpotifyManager()

# %% [markdown]
# ## 6. YouTube Music Integration with Quality Assessment

# %%
class YouTubeMusicManager:
    def __init__(self):
        self.client = None
        self.tracks = []
        
    def authenticate(self):
        """Initialize YouTube Music client"""
        try:
            if YTMUSIC_AUTH_FILE and Path(YTMUSIC_AUTH_FILE).exists():
                self.client = YTMusic(YTMUSIC_AUTH_FILE)
                logger.info("✅ YouTube Music authenticated with headers file")
            else:
                self.client = YTMusic()
                logger.info("✅ YouTube Music initialized (public access only)")
            return True
        except Exception as e:
            logger.error(f"❌ YouTube Music initialization failed: {e}")
            return False
    
    def search_candidates(self, track: Track) -> List[YouTubeCandidate]:
        """Search for multiple candidates for a track with quality assessment"""
        candidates = []
        
        try:
            # Try multiple search strategies
            search_queries = [
                f"{track.artist} {track.name}",
                f"{track.name} {track.artist}",
                f'"{track.name}" "{track.artist}"'
            ]
            
            seen_video_ids = set()
            
            for query in search_queries:
                try:
                    # Search in songs first (higher quality)
                    results = self.client.search(query, filter='songs', limit=MAX_YT_CANDIDATES)
                    
                    for result in results:
                        if result['videoId'] not in seen_video_ids:
                            seen_video_ids.add(result['videoId'])
                            candidate = self._create_candidate_from_result(result, 'song')
                            if candidate:
                                candidates.append(candidate)
                    
                    # Then search in videos if we need more candidates
                    if len(candidates) < MAX_YT_CANDIDATES:
                        results = self.client.search(query, filter='videos', limit=MAX_YT_CANDIDATES - len(candidates))
                        
                        for result in results:
                            if result['videoId'] not in seen_video_ids:
                                seen_video_ids.add(result['videoId'])
                                candidate = self._create_candidate_from_result(result, 'video')
                                if candidate:
                                    candidates.append(candidate)
                
                except Exception as e:
                    logger.warning(f"Search failed for query '{query}': {e}")
                    continue
                
                if len(candidates) >= MAX_YT_CANDIDATES:
                    break
            
            # Calculate quality scores for each candidate
            for candidate in candidates:
                candidate.quality_score = self._calculate_quality_score(candidate, track)
            
            # Sort by quality score
            candidates.sort(key=lambda x: x.quality_score, reverse=True)
            
            logger.info(f"Found {len(candidates)} candidates for: {track}")
            
        except Exception as e:
            logger.error(f"❌ Error searching for {track}: {e}")
        
        return candidates[:MAX_YT_CANDIDATES]
    
    def _create_candidate_from_result(self, result: dict, result_type: str) -> Optional[YouTubeCandidate]:
        """Create a YouTubeCandidate from search result"""
        try:
            # Extract basic info
            video_id = result.get('videoId', '')
            title = result.get('title', '')
            
            # Handle different result structures
            if result_type == 'song':
                artists = result.get('artists', [])
                artist = ', '.join([a.get('name', '') for a in artists]) if artists else ''
                duration_seconds = self._parse_duration(result.get('duration', ''))
                
                # For songs, channel info might be in different places
                channel_name = ''
                if artists:
                    channel_name = artists[0].get('name', '')
                
            else:  # video
                artist = result.get('channel', {}).get('name', '') if result.get('channel') else ''
                duration_seconds = self._parse_duration(result.get('duration', ''))
                channel_name = artist
            
            # Determine if it's official/verified
            is_official = self._is_official_upload(title, channel_name, artist)
            is_music = result_type == 'song' or 'music' in title.lower()
            
            return YouTubeCandidate(
                video_id=video_id,
                title=title,
                artist=artist,
                duration_seconds=duration_seconds,
                view_count=result.get('views', {}).get('text', '0').replace(',', '').replace(' views', '') if result.get('views') else '0',
                channel_name=channel_name,
                is_official=is_official,
                is_music=is_music,
                quality_score=0.0  # Will be calculated later
            )
            
        except Exception as e:
            logger.warning(f"Failed to create candidate from result: {e}")
            return None
    
    def _parse_duration(self, duration_str: str) -> int:
        """Parse duration string to seconds"""
        if not duration_str:
            return 0
        
        try:
            # Handle formats like "3:45", "1:23:45", etc.
            parts = duration_str.split(':')
            if len(parts) == 2:  # MM:SS
                return int(parts[0]) * 60 + int(parts[1])
            elif len(parts) == 3:  # HH:MM:SS
                return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            else:
                return int(duration_str)  # Just seconds
        except:
            return 0
    
    def _is_official_upload(self, title: str, channel_name: str, artist: str) -> bool:
        """Determine if this is likely an official upload"""
        title_lower = title.lower()
        channel_lower = channel_name.lower()
        artist_lower = artist.lower()
        
        # Official indicators
        official_indicators = [
            'official',
            'vevo',
            'records',
            'music',
            '- topic',
            'official video',
            'official audio'
        ]
        
        # Check if artist name is in channel name (strong indicator)
        if artist_lower and artist_lower in channel_lower:
            return True
        
        # Check for official indicators
        for indicator in official_indicators:
            if indicator in title_lower or indicator in channel_lower:
                return True
        
        return False
    
    def _calculate_quality_score(self, candidate: YouTubeCandidate, original_track: Track) -> float:
        """Calculate quality score for a candidate"""
        score = 0.0
        
        # Official artist channel (highest priority)
        if candidate.is_official:
            if any(indicator in candidate.channel_name.lower() for indicator in ['vevo', 'records']):
                score += QUALITY_WEIGHTS['official_artist']
            elif 'official' in candidate.title.lower():
                score += QUALITY_WEIGHTS['youtube_music']
            else:
                score += QUALITY_WEIGHTS['verified_channel']
        
        # Topic channels (auto-generated, usually high quality)
        if '- topic' in candidate.channel_name.lower():
            score += QUALITY_WEIGHTS['topic_channel']
        
        # Duration matching
        if original_track.duration_ms > 0:
            original_seconds = original_track.duration_ms // 1000
            duration_diff = abs(original_seconds - candidate.duration_seconds)
            if duration_diff <= 5:
                score += QUALITY_WEIGHTS['exact_duration']
            elif duration_diff <= 15:
                score += QUALITY_WEIGHTS['exact_duration'] * 0.5
        
        # View count (popularity indicator)
        try:
            view_count = int(str(candidate.view_count).replace(',', '').replace(' views', ''))
            if view_count > 1000000:  # 1M+ views
                score += QUALITY_WEIGHTS['high_views']
            elif view_count > 100000:  # 100K+ views
                score += QUALITY_WEIGHTS['high_views'] * 0.5
        except:
            pass
        
        # Audio quality indicators in title
        audio_quality_terms = ['hd', 'hq', 'high quality', '320', 'flac', 'lossless']
        if any(term in candidate.title.lower() for term in audio_quality_terms):
            score += QUALITY_WEIGHTS['audio_quality']
        
        # Music-specific content
        if candidate.is_music:
            score += 20
        
        return score

# Initialize YouTube Music
ytmusic_manager = YouTubeMusicManager()

# %% [markdown]
# ## 7. Download Manager with Quality Prioritization

# %%
class DownloadManager:
    def __init__(self):
        self.processed_tracks = set()
        self.failed_downloads = []
        self.successful_downloads = []
        
    def download_track(self, track: Track, youtube_candidate: YouTubeCandidate, attempt: int = 1) -> bool:
        """Download a single track with retry logic"""
        
        if attempt > RETRY_ATTEMPTS:
            logger.error(f"❌ Failed to download after {RETRY_ATTEMPTS} attempts: {track}")
            self.failed_downloads.append({
                'track': track.to_dict(),
                'candidate': youtube_candidate.__dict__,
                'reason': 'Max retries exceeded'
            })
            return False
        
        try:
            # Create safe filename
            safe_name = safe_filename(f"{track.artist} - {track.name}")
            output_path = DOWNLOAD_DIR / f"{safe_name}.%(ext)s"
            
            # Configure yt-dlp for high quality
            ydl_opts = {
                'format': 'bestaudio[ext=m4a]/bestaudio[ext=mp3]/bestaudio/best',
                'outtmpl': str(output_path),
                'extractaudio': True,
                'audioformat': 'mp3',
                'audioquality': '0',  # Best quality
                'embed_thumbnail': True,
                'add_metadata': True,
                'writesubtitles': False,
                'writeautomaticsub': False,
                'ignoreerrors': False,
                'no_warnings': False,
                'quiet': True,
                'retries': 3,
                'fragment_retries': 3,
                'skip_unavailable_fragments': True,
                'extract_flat': False,
                'writethumbnail': False,
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '320',
                }]
            }
            
            url = f"https://www.youtube.com/watch?v={youtube_candidate.video_id}"
            
            logger.info(f"⬇️ Downloading: {track} (Quality: {youtube_candidate.quality_score:.1f})")
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            
            # Add metadata
            final_path = output_path.with_suffix('.mp3')
            self._add_metadata(final_path, track, youtube_candidate)
            
            logger.info(f"✅ Successfully downloaded: {track}")
            self.successful_downloads.append({
                'track': track.to_dict(),
                'candidate': youtube_candidate.__dict__,
                'file_path': str(final_path)
            })
            return True
            
        except Exception as e:
            logger.warning(f"⚠️ Download attempt {attempt} failed for {track}: {e}")
            time.sleep(2 ** attempt)  # Exponential backoff
            return self.download_track(track, youtube_candidate, attempt + 1)
    
    def _add_metadata(self, file_path: Path, track: Track, youtube_candidate: YouTubeCandidate):
        """Add ID3 metadata to the downloaded file"""
        try:
            audiofile = eyed3.load(str(file_path))
            if audiofile and audiofile.tag:
                audiofile.tag.title = track.name
                audiofile.tag.artist = track.artist
                audiofile.tag.album = track.album
                audiofile.tag.comments.set(f"Downloaded from: {youtube_candidate.channel_name}")
                audiofile.tag.save()
                logger.debug(f"✅ Added metadata to: {file_path.name}")
        except Exception as e:
            logger.warning(f"⚠️ Failed to add metadata to {file_path}: {e}")
    
    def generate_report(self) -> str:
        """Generate a detailed download report"""
        report = f"""
# Music Download Report
Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}

## Summary
- **Successful Downloads**: {len(self.successful_downloads)}
- **Failed Downloads**: {len(self.failed_downloads)}
- **Download Directory**: {DOWNLOAD_DIR}

## Successful Downloads
"""
        
        for item in self.successful_downloads:
            track = item['track']
            candidate = item['candidate']
            report += f"✅ **{track['artist']} - {track['name']}**\n"
            report += f"   - Source: {candidate['channel_name']}\n"
            report += f"   - Quality Score: {candidate['quality_score']:.1f}\n"
            report += f"   - File: {Path(item['file_path']).name}\n\n"
        
        if self.failed_downloads:
            report += "\n## Failed Downloads\n"
            for item in self.failed_downloads:
                track = item['track']
                report += f"❌ **{track['artist']} - {track['name']}**\n"
                report += f"   - Reason: {item['reason']}\n\n"
        
        return report

# Initialize download manager
download_manager = DownloadManager()

# %% [markdown]
# ## 8. Main Sync Logic with AI Matching

# %%
class MusicSyncOrchestrator:
    def __init__(self):
        self.spotify = spotify_manager
        self.ytmusic = ytmusic_manager
        self.downloader = download_manager
        self.ollama = ollama
        
    def sync_music_library(self, include_liked=True, include_playlists=False):
        """Main synchronization process"""
        logger.info("🎵 Starting Music Library Sync...")
        
        # Step 1: Get Spotify tracks
        spotify_tracks = []
        
        if include_liked:
            liked_tracks = self.spotify.get_liked_songs()
            spotify_tracks.extend(liked_tracks)
        
        if include_playlists:
            playlist_tracks = self.spotify.get_all_playlists()
            spotify_tracks.extend(playlist_tracks)
        
        # Remove duplicates from Spotify
        unique_spotify_tracks = self._deduplicate_tracks(spotify_tracks)
        logger.info(f"📊 Processing {len(unique_spotify_tracks)} unique Spotify tracks")
        
        # Step 2: Process each track
        matches_found = []
        no_matches = []
        
        for i, track in enumerate(unique_spotify_tracks, 1):
            logger.info(f"🔍 Processing {i}/{len(unique_spotify_tracks)}: {track}")
            
            # Find YouTube candidates
            candidates = self.ytmusic.search_candidates(track)
            
            if not candidates:
                logger.warning(f"⚠️ No YouTube candidates found for: {track}")
                no_matches.append(track)
                continue
            
            # Use AI to find the best match
            if self.ollama.is_available():
                ai_matches = self.ollama.analyze_song_similarity(track, candidates)
                
                if ai_matches and ai_matches[0][1] >= SIMILARITY_THRESHOLD:
                    best_candidate = ai_matches[0][0]
                    similarity_score = ai_matches[0][1]
                    logger.info(f"🤖 AI Match found (similarity: {similarity_score:.2f}): {best_candidate}")
                    matches_found.append((track, best_candidate, similarity_score))
                else:
                    logger.warning(f"🤖 AI similarity too low for: {track}")
                    no_matches.append(track)
            else:
                # Fallback to quality-based selection
                best_candidate = candidates[0]  # Already sorted by quality score
                logger.info(f"🎯 Quality-based match: {best_candidate} (score: {best_candidate.quality_score:.1f})")
                matches_found.append((track, best_candidate, 0.8))  # Assume reasonable similarity
            
            # Small delay to be respectful to APIs
            time.sleep(0.5)
        
        logger.info(f"✅ Found {len(matches_found)} matches, {len(no_matches)} without matches")
        
        # Step 3: Download matched tracks
        if matches_found:
            logger.info("⬇️ Starting downloads...")
            self._download_matches(matches_found)
        
        # Step 4: Generate report
        report = self.downloader.generate_report()
        
        # Save report to file
        report_path = Path("music_sync_report.md")
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(report)
        
        logger.info(f"📋 Report saved to: {report_path}")
        
        return {
            'matches_found': len(matches_found),
            'no_matches': len(no_matches),
            'successful_downloads': len(self.downloader.successful_downloads),
            'failed_downloads': len(self.downloader.failed_downloads),
            'report_path': str(report_path)
        }
    
    def _deduplicate_tracks(self, tracks: List[Track]) -> List[Track]:
        """Remove duplicate tracks based on name and artist"""
        seen = set()
        unique_tracks = []
        
        for track in tracks:
            # Create a signature for deduplication
            signature = f"{track.name.lower().strip()}|{track.artist.lower().strip()}"
            
            if signature not in seen:
                seen.add(signature)
                unique_tracks.append(track)
        
        logger.info(f"🔄 Deduplicated {len(tracks)} -> {len(unique_tracks)} tracks")
        return unique_tracks
    
    def _download_matches(self, matches: List[Tuple[Track, YouTubeCandidate, float]]):
        """Download all matched tracks with threading"""
        
        def download_single_match(match_data):
            track, candidate, similarity = match_data
            try:
                success = self.downloader.download_track(track, candidate)
                return success
            except Exception as e:
                logger.error(f"❌ Unexpected error downloading {track}: {e}")
                return False
        
        # Use ThreadPoolExecutor for concurrent downloads
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            future_to_match = {executor.submit(download_single_match, match): match for match in matches}
            
            for future in as_completed(future_to_match):
                match = future_to_match[future]
                track = match[0]
                try:
                    success = future.result()
                    if success:
                        logger.info(f"✅ Completed: {track}")
                    else:
                        logger.warning(f"⚠️ Failed: {track}")
                except Exception as e:
                    logger.error(f"❌ Thread error for {track}: {e}")

# Initialize orchestrator
sync_orchestrator = MusicSyncOrchestrator()

print("🎵 Music Sync Orchestrator ready!")

# %% [markdown]
# ## 9. Interactive Analysis and Preview Functions

# %%
def preview_track_candidates(track_name: str, artist_name: str, max_candidates: int = 3):
    """Preview YouTube candidates for a specific track"""
    
    track = Track(name=track_name, artist=artist_name)
    
    print(f"\n🔍 Searching candidates for: {track}")
    print("=" * 50)
    
    candidates = ytmusic_manager.search_candidates(track)
    
    if not candidates:
        print("❌ No candidates found!")
        return
    
    print(f"Found {len(candidates)} candidates:\n")
    
    for i, candidate in enumerate(candidates[:max_candidates], 1):
        print(f"**Candidate {i}:**")
        print(f"  📹 Title: {candidate.title}")
        print(f"  👤 Artist: {candidate.artist}")
        print(f"  📺 Channel: {candidate.channel_name}")
        print(f"  ⏱️  Duration: {candidate.duration_seconds // 60}:{candidate.duration_seconds % 60:02d}")
        print(f"  👁️  Views: {candidate.view_count:,}")
        print(f"  ✅ Official: {candidate.is_official}")
        print(f"  🎵 Music: {candidate.is_music}")
        print(f"  ⭐ Quality Score: {candidate.quality_score:.1f}")
        print(f"  🔗 URL: https://youtube.com/watch?v={candidate.video_id}")
        print()
    
    # If Ollama is available, show AI analysis
    if ollama.is_available():
        print("🤖 AI Similarity Analysis:")
        print("-" * 30)
        
        ai_matches = ollama.analyze_song_similarity(track, candidates[:max_candidates])
        
        for candidate, similarity in ai_matches:
            print(f"  {candidate.title} - Similarity: {similarity:.2f}")
        
        if ai_matches:
            best_match = ai_matches[0]
            print(f"\n🎯 Best AI Match: {best_match[0].title} (Score: {best_match[1]:.2f})")

def analyze_spotify_library_sample(sample_size: int = 5):
    """Analyze a sample of your Spotify library"""
    
    print(f"📊 Analyzing {sample_size} tracks from your Spotify library...")
    print("=" * 60)
    
    if not spotify_manager.client:
        print("❌ Please authenticate with Spotify first!")
        return
    
    # Get a sample of liked songs
    liked_songs = spotify_manager.get_liked_songs()
    
    if not liked_songs:
        print("❌ No liked songs found!")
        return
    
    # Take a sample
    import random
    sample_tracks = random.sample(liked_songs, min(sample_size, len(liked_songs)))
    
    for i, track in enumerate(sample_tracks, 1):
        print(f"\n**Track {i}/{len(sample_tracks)}:**")
        print(f"  🎵 Name: {track.name}")
        print(f"  👤 Artist: {track.artist}")
        print(f"  💿 Album: {track.album}")
        print(f"  ⏱️  Duration: {format_duration(track.duration_ms)}")
        print(f"  📈 Popularity: {track.popularity}/100")
        
        # Quick candidate search
        candidates = ytmusic_manager.search_candidates(track)
        if candidates:
            best_candidate = candidates[0]
            print(f"  🎯 Best YT Match: {best_candidate.title}")
            print(f"     Channel: {best_candidate.channel_name}")
            print(f"     Quality Score: {best_candidate.quality_score:.1f}")
        else:
            print("  ❌ No YouTube candidates found")

def test_ai_matching(track_name: str, artist_name: str):
    """Test AI matching for a specific track"""
    
    if not ollama.is_available():
        print("❌ Ollama is not available. Please start Ollama with Gemma model.")
        return
    
    track = Track(name=track_name, artist=artist_name)
    candidates = ytmusic_manager.search_candidates(track)
    
    if not candidates:
        print(f"❌ No candidates found for: {track}")
        return
    
    print(f"🤖 Testing AI matching for: {track}")
    print("=" * 50)
    
    ai_matches = ollama.analyze_song_similarity(track, candidates)
    
    print("AI Analysis Results:")
    print("-" * 20)
    
    for candidate, similarity in ai_matches:
        status = "✅ MATCH" if similarity >= SIMILARITY_THRESHOLD else "❌ NO MATCH"
        print(f"{status} {similarity:.2f} - {candidate.title}")
        print(f"        Channel: {candidate.channel_name}")
        print(f"        Quality: {candidate.quality_score:.1f}")
        print()
    
    if ai_matches and ai_matches[0][1] >= SIMILARITY_THRESHOLD:
        print(f"🎯 Best Match: {ai_matches[0][0].title}")
        print(f"   Confidence: {ai_matches[0][1]:.2f}")
    else:
        print("⚠️ No suitable matches found")

print("🔍 Analysis functions ready!")
print("\nTry these functions:")
print("• preview_track_candidates('Song Name', 'Artist Name')")
print("• analyze_spotify_library_sample(10)")
print("• test_ai_matching('Song Name', 'Artist Name')")

# %% [markdown]
# ## 10. Authentication and Setup

# %%
def setup_authentication():
    """Setup authentication for all services"""
    
    print("🔐 Setting up authentication...")
    print("=" * 40)
    
    # Check Spotify credentials
    if not SPOTIFY_CLIENT_ID or SPOTIFY_CLIENT_ID == "your_spotify_client_id_here":
        print("❌ Please update SPOTIFY_CLIENT_ID in the configuration section")
        return False
    
    if not SPOTIFY_CLIENT_SECRET or SPOTIFY_CLIENT_SECRET == "your_spotify_client_secret_here":
        print("❌ Please update SPOTIFY_CLIENT_SECRET in the configuration section")
        return False
    
    # Authenticate Spotify
    print("🎵 Authenticating with Spotify...")
    if not spotify_manager.authenticate():
        return False
    
    # Authenticate YouTube Music
    print("📺 Initializing YouTube Music...")
    if not ytmusic_manager.authenticate():
        return False
    
    # Check Ollama
    print("🤖 Checking Ollama availability...")
    if ollama.is_available():
        print("✅ Ollama is ready with Gemma model")
    else:
        print("⚠️ Ollama not available - will use fallback matching")
    
    print("\n✅ Authentication setup complete!")
    return True

def check_dependencies():
    """Check if all required dependencies are installed"""
    
    required_packages = {
        'spotipy': 'Spotify API client',
        'ytmusicapi': 'YouTube Music API client', 
        'yt_dlp': 'YouTube downloader',
        'eyed3': 'Audio metadata editor',
        'requests': 'HTTP client',
        'pandas': 'Data analysis'
    }
    
    print("📦 Checking dependencies...")
    print("=" * 30)
    
    missing_packages = []
    
    for package, description in required_packages.items():
        try:
            __import__(package)
            print(f"✅ {package} - {description}")
        except ImportError:
            print(f"❌ {package} - {description} (MISSING)")
            missing_packages.append(package)
    
    if missing_packages:
        print(f"\n❌ Missing packages: {', '.join(missing_packages)}")
        print("Install with: pip install " + " ".join(missing_packages))
        return False
    
    print("\n✅ All dependencies satisfied!")
    return True

# Run initial checks
print("🚀 Running initial setup checks...")
check_dependencies()

# %% [markdown]
# ## 11. Main Execution Cell - Run Your Sync!

# %%
def run_music_sync(include_liked=True, include_playlists=False, dry_run=False):
    """
    Main function to run the music sync
    
    Args:
        include_liked: Include liked songs from Spotify
        include_playlists: Include playlist tracks from Spotify  
        dry_run: Only analyze, don't actually download
    """
    
    print("🎵 MUSIC LIBRARY SYNC")
    print("=" * 50)
    
    # Setup authentication
    if not setup_authentication():
        print("❌ Authentication failed. Please check your credentials.")
        return
    
    if dry_run:
        print("🔍 DRY RUN MODE - No downloads will be performed")
    
    # Start the sync process
    try:
        if dry_run:
            # Just analyze the first few tracks
            print("\n📊 Analyzing your library (sample)...")
            analyze_spotify_library_sample(5)
        else:
            # Full sync
            results = sync_orchestrator.sync_music_library(
                include_liked=include_liked,
                include_playlists=include_playlists
            )
            
            print("\n🎉 SYNC COMPLETED!")
            print("=" * 30)
            print(f"📊 Matches found: {results['matches_found']}")
            print(f"✅ Successful downloads: {results['successful_downloads']}")
            print(f"❌ Failed downloads: {results['failed_downloads']}")
            print(f"📋 Report saved: {results['report_path']}")
            
            return results
    
    except KeyboardInterrupt:
        print("\n⏹️ Sync interrupted by user")
    except Exception as e:
        logger.error(f"❌ Sync failed: {e}")
        print(f"❌ Sync failed: {e}")

# %% [markdown]
# ## 🚀 READY TO RUN!
# 
# **Before running, make sure you've updated:**
# 1. `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET` 
# 2. Optionally: `YTMUSIC_AUTH_FILE` for full YouTube Music access
# 3. Start Ollama with: `ollama run gemma`
# 
# **Then run one of these:**

# %%
# UNCOMMENT ONE OF THESE TO RUN:

# 1. DRY RUN - Just analyze, don't download
# run_music_sync(include_liked=True, include_playlists=False, dry_run=True)

# 2. SYNC LIKED SONGS ONLY
# run_music_sync(include_liked=True, include_playlists=False, dry_run=False)

# 3. SYNC EVERYTHING (liked songs + playlists)  
# run_music_sync(include_liked=True, include_playlists=True, dry_run=False)

# 4. TEST A SPECIFIC SONG
# preview_track_candidates("Bohemian Rhapsody", "Queen")

print("🎵 Ready to sync! Uncomment one of the lines above to start.")

# %% [markdown]
# ## 12. Utility Functions for Manual Operations

# %%
def download_single_track(track_name: str, artist_name: str, force_download=False):
    """Download a single track manually"""
    
    track = Track(name=track_name, artist=artist_name)
    
    print(f"⬇️ Manual download: {track}")
    print("=" * 40)
    
    # Check if already downloaded
    safe_name = safe_filename(f"{artist_name} - {track_name}")
    potential_file = DOWNLOAD_DIR / f"{safe_name}.mp3"
    
    if potential_file.exists() and not force_download:
        print(f"✅ File already exists: {potential_file}")
        print("Use force_download=True to re-download")
        return
    
    # Search for candidates
    candidates = ytmusic_manager.search_candidates(track)
    
    if not candidates:
        print("❌ No YouTube candidates found!")
        return
    
    # Show candidates and let AI choose or use best quality
    print(f"Found {len(candidates)} candidates:")
    for i, candidate in enumerate(candidates, 1):
        print(f"{i}. {candidate.title} - {candidate.channel_name} (Quality: {candidate.quality_score:.1f})")
    
    # Use AI if available
    if ollama.is_available():
        ai_matches = ollama.analyze_song_similarity(track, candidates)
        if ai_matches and ai_matches[0][1] >= SIMILARITY_THRESHOLD:
            best_candidate = ai_matches[0][0]
            print(f"\n🤖 AI selected: {best_candidate.title} (Similarity: {ai_matches[0][1]:.2f})")
        else:
            best_candidate = candidates[0]
            print(f"\n🎯 Quality-based selection: {best_candidate.title}")
    else:
        best_candidate = candidates[0]
        print(f"\n🎯 Quality-based selection: {best_candidate.title}")
    
    # Download
    success = download_manager.download_track(track, best_candidate)
    
    if success:
        print(f"✅ Successfully downloaded: {track}")
    else:
        print(f"❌ Download failed: {track}")

def list_downloaded_files():
    """List all downloaded music files"""
    
    music_files = list(DOWNLOAD_DIR.glob("*.mp3"))
    
    print(f"🎵 Downloaded Music Files ({len(music_files)} total)")
    print("=" * 50)
    
    if not music_files:
        print("No music files found in download directory")
        return
    
    for file_path in sorted(music_files):
        file_size = file_path.stat().st_size / (1024 * 1024)  # MB
        print(f"🎵 {file_path.name} ({file_size:.1f} MB)")

def cleanup_downloads():
    """Clean up partial or failed downloads"""
    
    print("🧹 Cleaning up download directory...")
    
    # Remove .part files (incomplete downloads)
    part_files = list(DOWNLOAD_DIR.glob("*.part"))
    for file_path in part_files:
        file_path.unlink()
        print(f"🗑️ Removed partial file: {file_path.name}")
    
    # Remove .temp files
    temp_files = list(DOWNLOAD_DIR.glob("*.temp"))
    for file_path in temp_files:
        file_path.unlink()
        print(f"🗑️ Removed temp file: {file_path.name}")
    
    print("✅ Cleanup complete!")

def export_spotify_library_to_csv():
    """Export your Spotify library to CSV for analysis"""
    
    if not spotify_manager.client:
        print("❌ Please authenticate with Spotify first!")
        return
    
    print("📊 Exporting Spotify library to CSV...")
    
    # Get all tracks
    liked_songs = spotify_manager.get_liked_songs()
    playlist_tracks = spotify_manager.get_all_playlists()
    
    all_tracks = liked_songs + playlist_tracks
    
    # Convert to DataFrame
    track_data = [track.to_dict() for track in all_tracks]
    df = pd.DataFrame(track_data)
    
    # Save to CSV
    csv_path = Path("spotify_library.csv")
    df.to_csv(csv_path, index=False)
    
    print(f"✅ Exported {len(all_tracks)} tracks to: {csv_path}")
    
    # Show some stats
    print(f"\n📈 Library Statistics:")
    print(f"Total tracks: {len(all_tracks)}")
    print(f"Unique tracks: {df.drop_duplicates(['name', 'artist']).shape[0]}")
    print(f"Most common artist: {df['artist'].mode().iloc[0] if not df.empty else 'N/A'}")

print("🛠️ Manual operation functions ready!")
print("\nAvailable functions:")
print("• download_single_track('Song Name', 'Artist Name')")
print("• list_downloaded_files()")
print("• cleanup_downloads()")
print("• export_spotify_library_to_csv()")

# %%
print("🎵 MUSIC SYNC NOTEBOOK READY!")
print("=" * 50)
print("📋 Setup checklist:")
print("✅ 1. Update SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET")
print("✅ 2. Optionally set YTMUSIC_AUTH_FILE")  
print("✅ 3. Start Ollama: ollama run gemma")
print("✅ 4. Run: run_music_sync() with your preferred options")
print("\n🚀 Happy syncing!")