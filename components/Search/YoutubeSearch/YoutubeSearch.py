import os
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


   