import re

import eyed3
import requests
from eyed3.id3.frames import ImageFrame


def set_thumbnail(mp3_file, image_url) -> bool:
    response = requests.get(image_url)
    audiofile = eyed3.load(mp3_file)

    if response.status_code != 200:
        return False
    if not audiofile:
        return False
    if not audiofile.tag:
        return False
    audiofile.tag.images.set(ImageFrame.FRONT_COVER, response.content, "image/jpeg")
    print("setting thumbnail")
    audiofile.tag.save()
    return True


def get_song_title_artist(text):
    """
    This function attempts to extract the song title and artist from a string.

    Args:
     text: The string containing the song information.

    Returns:
     A dictionary containing the extracted song title and artist,
     or None if no song information is found.
    """
    # Use regular expressions to extract artist and title in various formats
    matches = re.search(r"(?P<artist>.*?)\s*-\s*(?P<title>.*)", text)
    if matches:
        return matches.groupdict()
    matches = re.search(r"(?P<title>.*?)\s*\(\s*(?P<artist>.*?)\s*\)", text)
    if matches:
        return matches.groupdict()
    return {"title": text, "artist": ""}
