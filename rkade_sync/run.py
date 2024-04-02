import os

import eyed3
import requests
from eyed3.id3 import Tag
from eyed3.id3.frames import ImageFrame
from helpers.media import YTVideo


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


def main():
    ROOT = "/Users/russellkim/personal/music"
    raw_directory = f"{ROOT}/raw"
    os.makedirs(raw_directory, exist_ok=True)

    # For each playlist
    playlist = "rekordbox_deep_house"
    final_directory = f"{ROOT}/playlists/{playlist}"
    os.makedirs(final_directory, exist_ok=True)

    # For song in playlist
    params = {
        "video_id": "jvGm_vZmBTg",
        "track": "Logo Queen",
        "artist": "So Inagawa",
        "album": "Logo Queen",
        "playlist": playlist,
        "comments": "Awesome!",
        "bpm": 122,
    }
    yt = YTVideo(**params)
    fp = yt.download_mp3(raw_directory=raw_directory, final_directory=final_directory)
    set_thumbnail(fp, yt.youtube.thumbnail_url)


if __name__ == "__main__":
    main()
