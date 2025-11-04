from pathlib import Path
from prefect import get_run_logger
from components.Search.DuckDuckGoSearch.DuckDuckGoSearch import DuckDuckGoSearch

class ImageCollector_V1:

    def __init__(self, rate_limit:int|float =2.0):
        self.client = DuckDuckGoSearch(rate_limit=rate_limit)
        self.valid_extensions = ('.png', '.jpg', 'jpeg', 'webp', 'tiff')


    def _check_dimensions(self, width: int|None, height: int|None, required_ratio: str, min_w: int, min_h: int) -> bool:
        """
        Checks if the image dimensions meet the required ratio AND minimum size.
        """
        
        # 1. Basic Dimension Validity Check
        # Use a safe return value here that will not allow the image to pass if dimensions are missing/zero.
        if None in (height, width) or 0 in (height, width): return False 

        # 2. Minimum Size Check (New Logic)
        if width < min_w or height < min_h: return False

        # 3. Aspect Ratio Check (Original Logic)
        required_ratio = required_ratio.lower()
        
        if required_ratio == "horizontal": return width > height
        elif required_ratio == "vertical": return height > width
        elif required_ratio == "square": return width == height
        
        # If an unknown ratio is requested, assume any ratio is fine (but min size still applies)
        return True

    def search_image(
        self, 
        query:str,
        save_path:str,
        n_results:int = 3,
        ratio:str = "horizontal", 
        min_w:int = 0, 
        min_h:int = 0,
        **kwargs
    ):
        result = self.client.search_images(query, num_results=n_results, **kwargs)

        for res in result:
            width, height = res.get('width', None), res.get('height', None)

            if not self._check_dimensions(width, height, ratio, min_w, min_h): 
                continue # Skip to the next image if checks fail

            try: 
                path = Path(self.client.download_image(res['image'], save_path))
                if path.suffix in self.valid_extensions: return str(path)
                else: raise ValueError('Bad extension')
            except: continue

        log = get_run_logger()
        log.warning(f'Unable to download images for query: {query}')
        return None
