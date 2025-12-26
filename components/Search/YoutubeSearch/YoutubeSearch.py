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
        :param save_path: The full path AND filename where the video should be saved, 
                          WITHOUT the file extension (e.g., './output/MyVideo').
        :return: The final, full path of the downloaded file (str), or None if download failed.
        """
        
        # 1. Check if save_path has an extension; if so, remove it for output template
        # This logic is kept to ensure save_path is always the base name
        if os.path.splitext(save_path)[1]:
            save_path = os.path.splitext(save_path)[0]

        # 2. Ensure Folder Exists
        # Use os.path.dirname to get the directory path from the full save_path string
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        
        # 3. Define the output file template - FIXED
        # This correctly uses the base path/filename and adds the extension placeholder.
        output_template = f"{save_path}.%(ext)s"

        # 4. Determine the final expected path (Since we force MP4 merge)
        final_full_path = f"{save_path}.mp4"

        # 5. Define the download options
        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best',
            
            # Use the fixed output template
            'outtmpl': output_template,
            
            # Ensures that the final merged file is an MP4
            'merge_output_format': 'mp4',
            
            # Prevents overwriting
            'noclobber': True,
            
            # --- Logging Fix ---
            # Set the custom logger to suppress all verbose messages
            'logger': YoutubeSearch.QuietLogger(),
            
            # Displays your custom progress during download
            # 'progress_hooks': [lambda d: print(f"Status: {d['status']}")], 
        }

        # print(f"\nAttempting to download video from: {url}") # Now silent
        # print(f"Saving to: {output_template}") # Now silent

        try:
            # print(f"\n--- Starting Download ---")
            # print(f"Target file: {final_full_path}")

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
                
            # print("Download successful!")
            return final_full_path
            
        except Exception as e:
            # Errors captured by the logger are also caught here
            print(f"An error occurred during download: {e}")
            return None
        

    class QuietLogger:
        """Silences yt-dlp's verbose logs and warnings, only printing errors."""
        def debug(self, msg):
            # Suppress debug/info messages (like [youtube] Extracting...)
            pass
        def warning(self, msg):
            # Suppress warning messages (like No supported JavaScript runtime)
            pass
        def error(self, msg):
            # Keep errors visible
            print(f"yt-dlp Error: {msg}")