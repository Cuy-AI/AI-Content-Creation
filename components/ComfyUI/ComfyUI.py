import json
import uuid
import time
import requests
from pathlib import Path
from typing import Dict, Any, Optional

class ComfyUI:

    """
    A client class to communicate with the ComfyUI API for
    running workflows and managing resources
    """
    
    def __init__(self, host: str = "localhost", port: int = 8000):
        self.host = host
        self.port = port
        
    def __del__(self):
        self.free_memory()

    @staticmethod
    def generate_client_id():
        return str(uuid.uuid4())
    

    # --- Workflow execution ---

    def run_workflow(self, prompt_workflow: Dict[str, Any], client_id: Optional[str] = None) -> Optional[Dict[str, Any]]:

        if not prompt_workflow:
            raise ValueError("prompt_workflow parameter is mandatory")

        # The structure sent to /prompt requires the workflow under the 'prompt' key
        payload = {
            "prompt": prompt_workflow,
            "client_id": client_id if client_id else ComfyUI.generate_client_id()
        }

        try:
            response = requests.post(f"http://{self.host}:{self.port}/prompt", json=payload, timeout=60)
            response.raise_for_status()  # Raise an exception for bad status codes (4xx or 5xx)
            
            result = response.json()
            return result

        except requests.exceptions.RequestException as e:
            print(f"Error connecting to ComfyUI or running workflow: {e}")
            return None
        


    def wait_for_completion(self, prompt_id:str, time_per_sleep:int = 3) -> Optional[Dict[str, Any]]:

        while True:

            time.sleep(time_per_sleep)
            response = requests.get(f"http://{self.host}:{self.port}/history/{prompt_id}")

            if response.status_code != 200:
                print(f"[WARN] Error checking status: {response.status_code}")
                continue

            try:
                status_data = response.json()
            except json.JSONDecodeError:
                print("[WARN] No JSON returned", end="\r", flush=True)
                continue

            if prompt_id in status_data:

                execution_data = status_data[prompt_id]

                if "status" in execution_data and execution_data["status"].get("completed", False):
                    print("Generation completed!")
                    return status_data
                
                if "status" in execution_data and execution_data["status"].get("error", None):
                    print(f"Error while executing: {execution_data["status"]["error"]}")
                    return None
            
            


    # --- Resource Management ---

    def free_memory(self, unload_models:bool = True, free_memory:bool = True) -> bool:

        url = f"http://{self.host}:{self.port}/free"
    
        payload = {
            "unload_models": unload_models,  # Critical: Forces unloading of large VRAM models
            "free_memory": free_memory     # Forces PyTorch internal cache cleanup
        }
        
        try:
            response = requests.post(url, json=payload)
            
            if response.status_code == 200: return True
            else: return False
                
        except requests.exceptions.RequestException as e:
            return False



    # --- Output Management ---
    
    def collect_images(self, status_data: Dict[str, Any], prompt_id: str, output_folder:str = "./") -> list:
        
        if prompt_id not in status_data or "outputs" not in status_data[prompt_id]: return None
        
        outputs = status_data[prompt_id]["outputs"]
        url = f"http://{self.host}:{self.port}/view"
        images = []

        for node_id, node_output in outputs.items():
            if "images" in node_output:
                for image_info in node_output["images"]:
                    filename = image_info["filename"]
                    subfolder = image_info.get("subfolder", "")

                    view_params = { "filename": filename, "type": "output" }
                    if subfolder: view_params["subfolder"] = subfolder

                    image_response = requests.get(url, params=view_params)

                    if image_response.status_code == 200:
                        output_file = Path(output_folder) / filename
                        output_file.parent.mkdir(parents=True, exist_ok=True)
                        with open(output_file, "wb") as f:
                            f.write(image_response.content)
                        images.append(str(output_file))
                    else:
                        print(f"[ERROR] Failed to download image {filename}: {image_response.status_code}")
                        continue
        
        return images
                        


