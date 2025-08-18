import os
import json
from lm.OpenRouteLM import OpenRouteLM

def test_openrouter():

    # Step 1: Create the model
    model_name = "openai/gpt-oss-20b:free"
    # model_name = "deepseek/deepseek-r1-distill-llama-70b:free" 
    # model_name = "meta-llama/llama-3.1-405b-instruct:free" 

    lm = OpenRouteLM(model_name)

    # Step 2: Change some parameters dynamically
    lm.set_parameters(
        temperature=1.2,  # Make it more creative
        max_tokens=2048,  # Longer output since it's a video script
    )

    # Step 3: Define a custom JSON schema for a video script
    video_script_schema = {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "caption": {"type": "string"},
            "resume": {"type": "string"},
            "number_of_scenes": {"type": "integer"},
            "scenes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "character": {"type": "string"},
                        "script": {"type": "string"},
                        "image_prompt": {"type": "string"}
                    },
                    "required": ["character", "script", "image_prompt"]
                }
            }
        },
        "required": ["title", "caption", "resume", "number_of_scenes", "scenes"]
    }

    # Inject schema into parameters
    lm.set_schema(video_script_schema)

    prompt = """
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

    # Step 5: Call generate
    result = lm.generate(prompt, fix_prompt_with_schema=False)

    # Save response (force UTF-8 encoding)
    try:

        # Fix the name
        fixed_name = model_name.replace('/', '_').replace(':', '_')
        fixed_location = f"testing/test_openrouter/{fixed_name}.json"

        # Save the response
        print(f"Saving response to {fixed_location}")
        with open(fixed_location, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        # Check if file was saved
        if os.path.exists(fixed_location):
            print(f"File saved successfully to {fixed_location}")
        else:
            print(f"File was not saved to {fixed_location}")

    except Exception as e:
        print(f"Error saving response: {e}")

    print("\n\nFull response:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
