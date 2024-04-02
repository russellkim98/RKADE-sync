from ytmusicapi import YTMusic, setup
import typing as T


class YTMusicClient(YTMusic):
    """
    YTMusic client for use in getting playlist information
    """

    def __init__(self, header_dict: T.Dict[str, str]):
        super().__init__(auth=header_dict)

    def return_top_video_match(self, song_name: str) -> T.Tuple[str, str]:
        """
        Return the top result
        """
        results = self.search(query=song_name, filter="songs", limit=10)
        result = results[0]
        return result["title"], result["videoId"].replace("&", "\\&")

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
