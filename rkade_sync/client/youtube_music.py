from ytmusicapi import YTMusic


class YouTubeMusicClient(YTMusic):
    def get_top_video_id(self, song_name):
        results = self.search(query=song_name, filter="songs")
        return results[0]["videoId"] if results else None

    def get_thumbnail_url(self, song_name):
        results = self.search(query=song_name, filter="songs")
        return results[0]["thumbnails"][-1]["url"] if results else None
