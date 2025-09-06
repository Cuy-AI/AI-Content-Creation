import os
import json
from classes.ContainerManager import ContainerManager


def test_openrouter():
    # Create the OpenRouter container
    openRouter_container = ContainerManager(image="openrouter:latest", port=8000, use_gpu = False)
    openRouter_container.start()

    # Create the OpenRouter component
    openRouter_client = openRouter_container.create_client()

    # Set model name (OpenRouter method)
    answer = openRouter_client.set_model_name(model_name="deepseek/deepseek-r1-distill-llama-70b:free")
    print("Set model answer", answer)

    # Set params (BaseAI method)
    answer = openRouter_client.set_params(temperature=0.7, max_tokens=2048)
    print("Set params answer", answer)

    # Get params (BaseAI method)
    params = openRouter_client.get_params()
    print("Get params answer", params)

    # Define challenging JSON schema for video script generation
    video_script_schema = {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "A catchy YouTube video title under 60 characters"
            },
            "caption": {
                "type": "string",
                "description": "A short, intriguing description, like a YouTube video caption without spoilers"
            },
            "resume": {
                "type": "string",
                "description": "A summary of the full story, including spoilers"
            },
            "number_of_scenes": {
                "type": "integer",
                "minimum": 10,
                "maximum": 15,
            },
            "scenes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "character": {
                            "type": "string",
                            "description": "The name of the character that is speaking or narrating during the scene"
                        },
                        "script": {
                            "type": "string",
                            "description": "The dialogue or narration for the scene"
                        },
                        "image_prompt": {
                            "type": "string",
                            "description": "A detailed, descriptive prompt for an AI image generator that captures the visual essence of the scene"
                        }
                    },
                    "required": ["character", "script", "image_prompt"]
                }
            }
        },
        "required": ["title", "caption", "resume", "number_of_scenes", "scenes"]
    }

    # Set schema (OpenRouter method)
    answer = openRouter_client.set_schema(schema=video_script_schema)
    print("Set schema answer", answer)

    answer = openRouter_client.get_schema()
    print("Get schema answer", answer)

    # Get container output dir:
    saved_output_host = openRouter_container.host_volume
    saved_output_container = openRouter_container.container_volume
    additional_path = "/output/openrouter/test03/example_output.json" # A sample additional path

    # Good prompt for generating a video script
    video_prompt = """
    You are a video scriptwriter. Craft a short, suspenseful story for a video script, targeting an audience aged 16 to 45.
    The story should be a modern tech thriller about a young coder who uncovers a global conspiracy hidden in an old app's code.
    The script must be engaging and immersive, with a sense of urgency and mystery.
    The script should have exactly 12 scenes.
    The output must strictly follow the provided JSON schema:
    - title
    - caption (a short, intriguing description, like a YouTube video caption without spoilers)
    - resume (a summary of the full story, including spoilers)
    - number_of_scenes
    - scenes (an array of scene objects)

    Each scene object must contain:
    - character (the character speaking or narrating)
    - script (the dialogue or narration for the scene)
    - image_prompt (a detailed, descriptive prompt for an AI image generator that captures the visual essence of the scene)
    """

    # Generate the video script
    result = openRouter_client.generate(prompt=video_prompt, save_path=saved_output_container+additional_path)
    print("Generation result:\n", result)

    # Check if output was saved
    saved_path = saved_output_host+additional_path
    if not os.path.exists(saved_path):
        raise FileNotFoundError(f"Output json file not found: {saved_path}")

    # Open saved output
    with open(saved_path, "r", encoding="utf-8") as f:
        json_output = json.load(f)

    print("Saved result:\n", json_output)


    # Stop containers
    openRouter_container.stop()
