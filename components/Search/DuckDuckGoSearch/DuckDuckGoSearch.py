import os
import time
import requests
import mimetypes
import trafilatura
from ddgs import DDGS


class RateLimiter:
    """Simple rate limiter to avoid hitting DuckDuckGo too fast."""
    def __init__(self, min_interval=1.0):
        self.min_interval = min_interval
        self.last_call = 0

    def wait(self):
        elapsed = time.time() - self.last_call
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self.last_call = time.time()



class DuckDuckGoSearch:
    def __init__(self, rate_limit=1.5):
        self.rate_limiter = RateLimiter(rate_limit)
        self.ddgs = DDGS()

    def search_web(self, query, num_results=10, region="wt-wt", safesearch="moderate"):
        """
        Perform a web search using DuckDuckGo.
        Returns: List of {title, href, body}
        """
        self.rate_limiter.wait()
        results = []
        for r in self.ddgs.text(query, region=region, safesearch=safesearch, max_results=num_results):
            results.append({
                "title": r.get("title"),
                "url": r.get("href"),
                "snippet": r.get("body")
            })
        return results

    def search_images(
            self, query, 
            num_results=10, 
            region="wt-wt", 
            safesearch="off", 
            size=None, 
            color=None, 
            type_image=None,
            layout=None,
            license_image=None,
    ):
        """
        Perform an image search using DuckDuckGo.
        Returns: List of {title, image, thumbnail, source}
        Optional filters: size, color, type_image
        """
        self.rate_limiter.wait()
        results = []
        for img in self.ddgs.images(
            query,
            region=region,
            safesearch=safesearch,
            size=size,          # "Small", "Medium", "Large", etc.
            color=color,        # "color", "Monochrome", etc.
            type_image=type_image,  # "photo", "clipart", "gif", etc.
            layout=layout,
            license_image=license_image,
            max_results=num_results
        ):
            results.append({
                "title": img.get("title"),
                "image": img.get("image"),
                "thumbnail": img.get("thumbnail"),
                "url": img.get("url"),
                "source": img.get("source"),
                "height": img.get("height"),
                "width": img.get("width"),
            })
        return results
    

    def extract_content(self, html, output_format="txt"):
        """
        Extract the main content from a given HTML using trafilatura.

        :param html: Raw HTML content as string
        :return: dict with extracted text
        """
        extracted = trafilatura.extract(html, output_format=output_format)
        return {"content": extracted}
        

    def download_html(self, url, output_path = None):
        """
        Download the raw HTML content of a webpage and save it to a file.

        :param url: URL of the webpage
        :param output_path: Path to save the downloaded HTML file
        :return: raw html
        """
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        raw_html = response.text

        if output_path:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(raw_html)

        return raw_html
        

    def download_image(self, url, output_path):
        """
        Download an image from a URL and save it with its original extension.
        Creates parent directories if they do not exist.
        :param url: Image URL
        :param output_path: Local file path (without extension required)
        :return: Final saved file path
        """
        response = requests.get(url, stream=True, timeout=10)
        response.raise_for_status()

        # Try to detect extension from HTTP headers
        content_type = response.headers.get("Content-Type", "")
        ext = mimetypes.guess_extension(content_type.split(";")[0]) if content_type else None

        # If no extension from headers, try from URL
        if not ext:
            ext = os.path.splitext(url.split("?")[0])[1]

        if not ext:
            raise ValueError("Could not determine image extension")

        # Ensure output_path has the correct extension
        base, _ = os.path.splitext(output_path)
        final_path = base + ext

        # Ensure parent directories exist
        os.makedirs(os.path.dirname(final_path), exist_ok=True)

        # Save the file as-is
        with open(final_path, "wb") as f:
            for chunk in response.iter_content(8192):
                f.write(chunk)

        return final_path
