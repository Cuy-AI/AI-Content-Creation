import os
import requests
from bs4 import BeautifulSoup
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


    def extract_content(self, url, ignore_tags=None, required_tags=None, only_required_tags=False):
        """
        Extract structured text content from a given URL, preserving order.
        :param url: The webpage URL
        :param ignore_tags: list of tags to ignore (e.g. ["script", "style", "footer"])
        :param required_tags: list of tags that must exist (e.g. ["title", "h1"])
        :param only_required_tags: if True, extract only required_tags; if False, extract all except ignored
        :return: list of dicts [{tag: "p", content: "..."}], in DOM order
        """

        if only_required_tags and not required_tags:
            raise ValueError(f"Only mandatory tags flag is active but no mandatory tags were given: {required_tags}")

        if ignore_tags is None:
            ignore_tags = ["script", "style", "noscript", "header", "footer", "meta", "link", "svg"]

        response = requests.get(url, timeout=10)
        response.raise_for_status()

        content_type = response.headers.get("Content-Type", "")
        if "html" not in content_type: # Not HTML, nothing to parse
            return []

        soup = BeautifulSoup(response.text, "html.parser")

        extracted = []

        # Flatten relevant tags from soup in order
        for element in soup.find_all(True):  # all tags
            tag = element.name

            # skip ignored tags
            if tag in ignore_tags: continue

            # Skip if not in required and only_required_tags = true
            if only_required_tags and tag not in required_tags: continue

            text = element.get_text(strip=True)
            if text: extracted.append({"tag": tag, "content": text})

        return extracted
