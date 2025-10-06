import json
from components.Search.GoogleSearchEngine.GoogleSearchEngine import GoogleSearchEngine

class ImageDownloader:

    def __init__(self):
        self.client = GoogleSearchEngine()

    def search_images(self, script:dict, save_path:str|None = None):
        
        resp = {}
        for idx, scene in enumerate(script['scenes']):
            query = scene['web_image']
            if query is None: continue

            answer = self.client.search(query, num=1, search_type="image")
            resp[idx] = answer[0]["link"]

        if save_path:
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(resp, f, indent=2, ensure_ascii=False)

        return resp


    def download_images(self, images_urls: dict, save_folder: str):
        
        resp = {}
        for idx, url in images_urls.items():
            save_path = save_folder + f'scene-{idx}'
            try:
                save_path = self.client.download_image(url, save_path)
                resp[idx] = save_path
            except:
                print(f'[ERROR] Unable to download image: {url}')
        
        save_path = save_folder + 'metadata.json'
        with open(save_path, "w", encoding="utf-8") as f:
            json.dump(resp, f, indent=2, ensure_ascii=False)

        return resp