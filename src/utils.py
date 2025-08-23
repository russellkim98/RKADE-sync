"""Utility functions for the application."""

def format_duration(ms: int) -> str:
    """Convert milliseconds to MM:SS format."""
    seconds = ms // 1000
    minutes = seconds // 60
    seconds = seconds % 60
    return f"{minutes}:{seconds:02d}"
