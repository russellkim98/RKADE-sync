"""Text processing utilities for music matching."""

import re
from typing import Any, Dict, List


def preprocess_text(text: str) -> str:
    """Normalize text for comparison by removing non-alphanumeric chars and lowercasing.

    Args:
        text: Text to preprocess

    Returns:
        Processed text with only alphanumeric characters and lowercased
    """
    if not text:
        return ""
    return re.sub(r"[^a-z0-9]", "", text.lower())


def safe_get(d: Dict[str, Any], keys: List[str], default: Any = None) -> Any:
    """Safely get nested dictionary values.

    Args:
        d: Dictionary to retrieve value from
        keys: List of keys to traverse
        default: Default value if key path doesn't exist

    Returns:
        Value at key path or default if not found
    """

    for key in keys:
        try:
            d = d[key]
        except (KeyError, TypeError):
            return default

    return d


def generate_fallback_search_query(track: Dict[str, Any]) -> str:
    """Create a search query from track metadata using heuristics.

    Args:
        track: Spotify track data

    Returns:
        Search query optimized for YouTube Music
    """
    artists = [a["name"] for a in track.get("artists", [])]
    album = safe_get(track, ["album", "name"], "")
    version_keywords = {"remaster", "deluxe", "live", "version", "edit", "mix", "bonus"}

    query_parts = [track.get("name", "")]
    if artists:
        query_parts.append(artists[0])
    if len(artists) > 1:
        query_parts.append(f"feat. {', '.join(artists[1:])}")
    if any(kw in album.lower() for kw in version_keywords):
        query_parts.append(album)

    return re.sub(r"\s+", " ", " ".join(query_parts)).strip()
