from pytube import YouTube


def main():
    url = "https://www.youtube.com/watch?v=jvGm_vZmBTg"
    video = YouTube(url)
    streams = video.streams


if __name__ == "__main__":
    main()
