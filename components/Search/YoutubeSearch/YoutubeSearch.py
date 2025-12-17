import os
import yt_dlp
from dotenv import load_dotenv
from googleapiclient.discovery import build

class YoutubeSearch:
    def __init__(self):

        # Load environment variables
        load_dotenv()
        self.api_key = os.getenv("GCP_YOUTUBE_SEARCH")
        if not self.api_key: raise ValueError("Missing GCP_YOUTUBE_SEARCH")

        # Create the service object
        self.youtube = build("youtube", "v3", developerKey=self.api_key) 

    def search(self, query, max_results=5):

        # Execute the search request
        request = self.youtube.search().list(
            q=query,            # The keyword search term
            part="snippet",     # Specifies the data parts to include (title, description, etc.)
            type="video",       # Filters results to videos only (not channels or playlists)
            maxResults=max_results
        )
        response = request.execute()

        videos = response.get("items", [])
        for i in range(len(videos)):
            videos[i].update({"url": f"https://www.youtube.com/watch?v={videos[i]['id']['videoId']}"})

        return videos


    def download_video(self, url, save_path = "./output"):
        """
        Downloads a video from a given URL using yt-dlp,
        saving it to a specified path with a custom filename.

        :param url: The URL of the video (e.g., YouTube URL).
        :param save_path: The directory where the video should be saved (without extension).
        """
        # 1. Ensure Folder Exists
        os.makedirs(os.path.dirname(save_path), exist_ok=True)

        # 2. Check if save_path has an extension; if so, remove it for output template
        if os.path.splitext(save_path)[1]:
            save_path = os.path.splitext(save_path)[0]

        # 3. Define the output file template
        # We use the 'outtmpl' option to specify the exact path and filename.
        # We include %(ext)s so yt-dlp can add the correct file extension (e.g., .mp4, .webm).
        output_template = os.path.join(save_path, f".%(ext)s")

        # 4. Define the download options
        ydl_opts = {
            # Selects the best video and audio streams, then merges them into an MP4 container.
            # This ensures high quality and wide compatibility.
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best',
            
            # Specifies the output template using the path and custom filename
            'outtmpl': output_template,
            
            # Ensures that the final merged file is an MP4
            'merge_output_format': 'mp4',
            
            # Prevents overwriting if a file with the same name already exists
            'noclobber': True,
            
            # Displays the progress during download
            'progress_hooks': [lambda d: print(f"Status: {d['status']}")], 
        }

        # print(f"\nAttempting to download video from: {url}")
        # print(f"Saving to: {output_template}")

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # The download method takes a list of URLs
                ydl.download([url])
            # print("Download successful!")
            return f'{save_path}.mp4'
            
        except Exception as e:
            print(f"An error occurred during download: {e}")
            return None