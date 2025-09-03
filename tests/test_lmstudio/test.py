import os
import json
from components.LM.LMStudio.LMStudio import LMStudio


def test_lmstudio():

    # 1) Create the Component and container
    lms = LMStudio()

    # 2) See what's available and what's loaded
    print("Available models:", lms.list_available_models())
    print("Loaded models:", lms.list_loaded_models())
    print("Current model:", lms.model)

    # 3) Load a specific model (with optional load-time config)
    model_id = "mistralai/mistral-nemo-instruct-2407"
    # model_id = "openai/gpt-oss-20b" # trash xd
    answ = lms.load_model(model_id, config={"contextLength": 8192})
    print("Load model:", answ)

    # 4) Inspect/override supported generation params
    answ = lms.set_params(temperature = 0.7)
    print("Set parameters:", answ)
    print("get parameters:", lms.get_params())


    # 5) (MANDATORY) Replace the structured output schema
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
                "type": "integer"
            },
            "scenes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "character": {
                            "type": "string",
                            "description": "The name of the character that is speaking or narrating during the scene",
                            "enum": ["David", "Lucy", "Narrator"]
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

    answ = lms.set_schema(video_script_schema)
    print(answ)

    # 6.1) Set volume path
    save_path = "volume_output/lmstudio/test02/output_chat.json"

    # 6.2) Generate (chat)
    messages = [
        {
            "role": "system",
            "content": "You are a helpful assistant that generates structured JSON outputs."
        },
        {
            "role": "user",
            "content": "Generate a YouTube video script in JSON format about 'The Rise and Fall of Blockbuster: How Netflix Changed Entertainment Forever'. Use the following characters: 'David', 'Lucy', 'Narrator'."
        },
    ]
    resp = lms.generate(messages = messages, save_path=save_path)
    print("Answer1:\n", resp)

    # Check if output was saved
    if not os.path.exists(save_path):
        raise FileNotFoundError(f"Output json file not found: {save_path}")

    # Open saved output
    with open(save_path, "r", encoding="utf-8") as f:
        json_output = json.load(f)

    print("Saved result:\n", json_output)

    # 7.1) Set volume path
    save_path = "volume_output/lmstudio/test02/output_prompt.json"

    # 7.2) Generate (text completion/prompt)
    prompt = """
    You are a video scriptwriter. Craft a short, suspenseful story for a video script, targeting an audience aged 16 to 45.
    The story should be a modern tech thriller about a young coder who uncovers a global conspiracy hidden in an old app's code.
    The script must be engaging and immersive, with a sense of urgency and mystery.
    The script should have exactly 12 scenes.
    Character of the story: 'David', 'Lucy', 'Narrator'
    The output must strictly follow the provided JSON schema:
    - title
    - caption (a short, intriguing description, like a YouTube video caption without spoilers)
    - resume (a summary of the full story, including spoilers)
    - number_of_scenes
    - scenes (an array of scene objects)

    Each scene object must contain:
    - character (the character speaking or narrating. I will give you the allowed characters on the json schema as an enum).
    - script (the dialogue or narration for the scene)
    - image_prompt (a detailed, descriptive prompt for an AI image generator that captures the visual essence of the scene)
    """
    resp2 = lms.generate(prompt = prompt, save_path=save_path)
    print("Answer2:\n", resp2)

    # Check if output was saved
    if not os.path.exists(save_path):
        raise FileNotFoundError(f"Output json file not found: {save_path}")

    # Open saved output
    with open(save_path, "r", encoding="utf-8") as f:
        json_output = json.load(f)

    print("Saved result:\n", json_output)

    # 8) Stop the server when you’re done
    answ = lms.eject_model(model_id)
    print(answ)

    answ = lms.stop_server()
    print(answ)