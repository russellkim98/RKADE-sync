import typing as T

from ytmusicapi import YTMusic, setup


class YTMusicClient(YTMusic):
    """
    YTMusic client for use in getting playlist information
    """

    def __init__(self, auth: str):
        super().__init__(auth=auth)

    def return_top_video_match(self, song_name: str) -> T.Tuple[str, str, str]:
        """
        Return the top result
        """
        results = self.search(query=song_name, filter="songs", limit=10)
        result = results[0]
        video_id = result["videoId"].replace("&", "\\&")
        title = result["title"]
        album = result["album"]["name"] if result["album"] else title
        return (video_id, title, album)

    def create_ytdlp_cmd(
        self,
        video_id: str,
        title: str,
        artist: str,
        archive_path: str,
        output_dir: str,
    ) -> str:
        """
        Create the ytdlp command
        """
        url = f"""https://www.youtube.com/watch?v={video_id}"""
        static = f"""yt-dlp --embed-thumbnail -f "ba" -x --audio-quality 0  --audio-format mp3 --download-archive {archive_path} """
        metadata = f"""--parse-metadata "{title} :%(meta_title)s" --parse-metadata "{artist} :%(meta_artist)s" --embed-metadata """
        output = f"""-o "{output_dir}/{title}.%(ext)s" "{url}" """
        command = static + metadata + output
        return command
