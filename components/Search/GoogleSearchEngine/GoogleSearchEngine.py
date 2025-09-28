import os
import requests
from dotenv import load_dotenv

class GoogleSearchEngine:
    def __init__(self):

        load_dotenv()
        self.api_key = os.getenv("GOOGLE_SEARCH_ENGINE_API_KEY")
        self.engine_id = os.getenv("GOOGLE_SEARCH_ENGINE_ID")

        if not self.api_key or not self.engine_id:
            raise ValueError("Missing GOOGLE_API_KEY or GOOGLE_ENGINE_ID in .env file")

        self.base_url = "https://www.googleapis.com/customsearch/v1"


    def search(self, query, num=5, search_type=None, **kwargs):
        """
        Run a Google Custom Search query.
        :param query: Search query string
        :param num: Number of results (max 10 per request)
        :param search_type: None for normal search, "image" for image search
        :param kwargs: 
            Extra API parameters (gl, hl, cr, siteSearch, siteSearchFilter, etc.)
            https://developers.google.com/custom-search/v1/reference/rest/v1/cse/list
        :return: List of dict results
        """
        params = {
            "key": self.api_key,
            "cx": self.engine_id,
            "q": query,
            "num": num
        }

        if search_type == "image": params["searchType"] = "image"

        # Merge extra parameters
        params.update(kwargs)

        response = requests.get(self.base_url, params=params)
        response.raise_for_status()
        data = response.json()

        results = []
        if "items" in data:
            for item in data["items"]:
                result = {
                    "title": item.get("title"),
                    "link": item.get("link"),
                    "snippet": item.get("snippet")
                }
                if search_type == "image":
                    result["thumbnail"] = item.get("image", {}).get("thumbnailLink")
                results.append(result)

        return results
