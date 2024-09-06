import asyncio
import typing as T
from concurrent.futures import ThreadPoolExecutor

from yt_dlp import YoutubeDL
from ytmusicapi import YTMusic

# Define the options dictionary
# Define the options that mirror the command line arguments
ydl_opts = {
    "cookiesfrombrowser": ("chrome",),
    "format": "ba",  # 'ba' means best audio only
    "postprocessors": [
        {
            "key": "FFmpegExtractAudio",
            "preferredcodec": "aac",  # Convert to m4a
            "preferredquality": 4,
        },
        {
            "key": "EmbedThumbnail",  # Embed thumbnail in audio file
            "already_have_thumbnail": False,  # Download the thumbnail
        },
    ],
    "writethumbnail": True,
    "outtmpl": "/Users/russellkim/personal/dev/RKADE-sync/.tmp/music/%(title)s.%(ext)s",  # Output filename template
    "parse_metadata": [
        {
            "source": "title",
            "regex": "%(artist)s - %(title)s",
        }
    ],
    "download_archive": "index.txt",  # Track downloaded files in index.txt
}


# Define a function to run YoutubeDL's download method
def download_video(url):
    with YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])


# Define an asynchronous wrapper for the download function
async def async_download_video(url, executor):
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(executor, download_video, url)


# Define a function to run multiple downloads asynchronously
async def download_videos(urls):
    # Create a ThreadPoolExecutor for running download tasks
    with ThreadPoolExecutor() as executor:
        tasks = [async_download_video(url, executor) for url in urls]
        await asyncio.gather(*tasks)


def url_generator(video_id: str) -> str:
    return f"https://music.youtube.com/watch?v={video_id}"


def return_all_urls(video_ids: T.List[str]) -> T.List[str]:
    return [url_generator(id) for id in video_ids]


def return_playlist_urls(playlist_id: str) -> T.List[str]:
    yt = YTMusic("/Users/russellkim/personal/dev/RKADE-sync/.tmp/oauth.json")
    tracks = yt.get_playlist(playlist_id, limit=None)["tracks"]
    video_ids = [t["videoId"] for t in tracks]

    return return_all_urls(video_ids)


playlists = {
    "rekordbox_house_deep": "PL2ue0QWGzM_vKGZdIPCFnRxArzsDOMATH",
    "rekordbox_house_deep_youtube": "PL2ue0QWGzM_tWpR1RnucXIIhMoJ7ZKUoe",
    "rekordbox_quiet": "PL2ue0QWGzM_ub97g-kjIb2YWSmqBLRbNs",
    "rekordbox_hiphop": "PL2ue0QWGzM_uSQ34PxGD6avYfOyZhA3wA",
    "rekordbox_chill": "PL2ue0QWGzM_u27fTNeJ-va-vlQFFqbwEC",
    "rekordbox_trap": "PL2ue0QWGzM_vt9Hn4b1KdOYvuFVxxLtCc",
    "rekordbox_dubstep": "PL2ue0QWGzM_tYVL9uJThYfdlLya-PZGAd",
    "rekordbox_house_speed": "PL2ue0QWGzM_uLfSoPPI_4qnmtBODIVTKH",
    "rekordbox_house_tech": "PL2ue0QWGzM_ukYszlIypG3twJTgDQRPTb",
    "rekordbox_house_bass": "PL2ue0QWGzM_uZeWC88vwFaJ-A7OqPoK4l",
    "rekordbox_techno": "PL2ue0QWGzM_sGhlXBbXvqI4bq2Wktdv0B",
    "rekordbox_techno_industrial": "PL2ue0QWGzM_t5mvXQ0ODDgAqS7IOpwJyg",
    "rekordbox_dnb": "PL2ue0QWGzM_v4OmcMO2vjN78VK6HYaAfN",
    "rekordbox_house_pop": "PL2ue0QWGzM_tyLDTzi6n_QFix7ff5aOkh",
}

urls = []

for name, id in playlists.items():
    urls.extend(return_playlist_urls(id))


# Run the asynchronous download tasks
if __name__ == "__main__":
    asyncio.run(download_videos(urls))
