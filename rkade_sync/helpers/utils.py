import re

import eyed3
import requests
from eyed3.id3.frames import ImageFrame


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


def set_thumbnail(mp3_file: str, image_url: str):
    """
    Sets the thumbnail for an MP3 file using an image URL.

    Args:
        mp3_file (str): Path to the MP3 file.
        image_url (str): URL of the image to use as thumbnail.
    """
    # Download the image
    response = requests.get(image_url, stream=True)
    if response.status_code == 200:
        image_data = response.content
        mime_type = response.headers.get("Content-Type")

        # Load the MP3 file
        audiofile = eyed3.load(mp3_file)

        # Add the ImageFrame to the MP3 file
        audiofile.tag.images.set(ImageFrame.FRONT_COVER, image_data, mime_type)  # type: ignore

        # Save the changes to the MP3 file
        audiofile.tag.save()  # type: ignore
        print(f"Thumbnail set for {mp3_file}")
    else:
        print(f"Error downloading image: {response.status_code}")
