import sys
import yt_dlp

def download_video(url):
    try:
        ydl_opts = {
            'format': 'bestvideo+bestaudio/best',
            'progress_hooks': [on_progress],
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        print("\nDownload completed!")
    except Exception as e:
        print(f"An error occurred: {e}")

def on_progress(d):
    if d['status'] == 'downloading':
        percentage = d['_percent_str']
        print(f"Downloading... {percentage}", end='\r')

def main():
    if len(sys.argv) > 1:
        url = sys.argv[1]
    else:
        url = input("Enter YouTube URL: ")
    download_video(url)

if __name__ == "__main__":
    main()