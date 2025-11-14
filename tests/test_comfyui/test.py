import os
import json
from components.ComfyUI.ComfyUI import ComfyUI

def test_comfyui():

    # ---Initialize the client ---
    comfy_client = ComfyUI()

    # Workflows are saved in JSON format. This is a highly optimized workflow (with a lightweight model for simple tasks):
    with open('components/ComfyUI/workflows/Luigi-ImageEditQwen2-Optimized2.json', 'r') as f:
        SIMPLE_TEXT_TO_IMAGE_WORKFLOW = json.load(f) # This is not actually a simple workflow...
        

    # --- Edit inputs ---
    current_path = os.getcwd()
    image_path = os.path.join(current_path, "volume/resources/images/comfyui/pic.png")
    print(f"Input Image: {image_path}")

    # Images are relative to the comfy ui input folder or you can use an absolute paths
    # SIMPLE_TEXT_TO_IMAGE_WORKFLOW["78"]["inputs"]["image"] = "ComfyUI_00002_cut.png"
    SIMPLE_TEXT_TO_IMAGE_WORKFLOW["78"]["inputs"]["image"] = image_path

    # --- The only way to edit prompts is locating the exact prompt node
    SIMPLE_TEXT_TO_IMAGE_WORKFLOW["111"]["inputs"]["prompt"] = "Remove the text 'Después de tanto los 3 de siempre' from the image. For the person on the left (in the maroon shirt): Change his pose to look like he's doing a silly dance move, perhaps with one arm dramatically thrown up in the air and the other hand holding his drink out to the side, a big grin on his face. For the person in the middle (in the denim shirt and glasses): Change his pose to look like he's caught mid-sneeze, with his eyes squeezed shut, mouth slightly open, and his drink slightly tilted as if he's about to spill it. For the person on the right (in the black t-shirt and glasses): Change his pose to look like he's trying to balance his drink on his head with a focused, slightly strained expression, perhaps with one hand outstretched for balance."

    # More steps for Ksampler just because is a difficutl edit
    # SIMPLE_TEXT_TO_IMAGE_WORKFLOW["3"]["inputs"]["steps"] = 8

    # --- Run workflow ---
    print("\n--- Running Direct Workflow ---")
    response = comfy_client.run_workflow(SIMPLE_TEXT_TO_IMAGE_WORKFLOW)
    prompt_id = response.get("prompt_id", None)
    print(f"prompt_id: {prompt_id}")

    # --- Waiting for completion ---
    print("\n--- Waiting for completion ---")
    status_data = comfy_client.wait_for_completion(prompt_id)
    print(f"Outputs: {status_data}")

    # --- Collect images ---
    print("\n--- Collect Output Images ---")
    output_folder = "volume/output/comfyui/test01/"
    images = comfy_client.collect_images(status_data, prompt_id, output_folder)
    print(f"Collected Images: {images}")

    # --- IMPORTANT: Unload Models and Cache ---
    print("\n--- Unloading Models/Cache ---")
    unload_success = comfy_client.free_memory()
    print(f"Unload operation successful: {unload_success}")