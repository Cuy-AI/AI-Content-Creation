import os
import json
from components.LM.LMStudio.LMStudio import LMStudio

'''
Tested models:
"mistralai/magistral-small-2509" -> Good but heavy and slow
"bytedance/seed-oss-36b" -> Good but heavy and slow
"mistralai/mistral-nemo-instruct-2407" -> Fast 
"openai/gpt-oss-20b" -> Trash xd
'''

def test_lmstudio():

    # 1) Create the Component and container
    lms = LMStudio()

    # 2) See what's available and what's loaded
    print("Available models:", lms.list_available_models())
    print("Loaded models:", lms.list_loaded_models())
    print("Current model:", lms.model)


    # TOPIC GENERATOR TEST ----------------------------------------------------------------------------------------

    # 3) Load a specific model (with optional load-time config)
    model_id = "mistralai/mistral-nemo-instruct-2407"
    answ = lms.load_model(model_id, config={"contextLength": 8192})
    print("Load model:", answ)

    # 4) Set preset parameters
    answ = lms.set_preset(preset_identifier='@local:test03-mistralai-mistral-nemo-instruct-2407') # Json schema is included here
    print("Set preset:", answ)
    print("Get preset:", lms.get_preset()) 

    # 5) Set volume path
    save_path = "volume/output/lmstudio/test03/output_chat.json"

    # 6) Generate (chat)
    messages = [
        {
            "role": "system",
            "content": "You are a creative social media strategist that generates engaging Reels video topic(s) for a given category and returns structured JSON outputs. The topics you generate must be a concise, high-level concept, not a catchy title, full sentence, or include hashtags. Reel Requirements: Each topic must be suitable for a fast-paced, 30-60 second short-form video. Ensure the concept has a clear potential hook to grab attention and a strong potential call-to-action (CTA) to encourage comments or shares."
        },
        {
            "role": "user",
            "content": "Suggest 10 unique, engaging Reels video topic(s) for the category: Cloud & Big Tech. Avoid these (already done) video topics: ['How Netflix handles millions of streams', 'How Google search works', 'AWS explained in 60 seconds', 'How YouTube manages billions of videos', 'What is serverless computing?']"
        },
    ]

    resp2 = lms.generate(messages = messages, save_path=save_path)
    print("\nAnswer1:")
    for k,v in resp2.items(): print(f"{k}: {v}")

    # Check if output was saved
    if not os.path.exists(save_path):
        raise FileNotFoundError(f"Output json file not found: {save_path}")

    # Open saved output
    with open(save_path, "r", encoding="utf-8") as f:
        json_output = json.load(f)

    print("Saved result:\n", json_output)

    # 7) Eject the model from ram when you’re done
    answ = lms.eject_model(model_id)
    print(answ)


    # SCRIPT GENERATOR TEST ----------------------------------------------------------------------------------------

    # 8) Load a specific model (with optional load-time config)
    model_id = "mistralai/magistral-small-2509"
    answ = lms.load_model(model_id, config={"contextLength": 8192})
    print("Load model:", answ)

    # 9) Set preset parameters
    answ = lms.set_preset(preset_identifier='@local:test02-mistralai-magistral-small-2509') # Json schema is included here
    print("Set preset:", answ)
    print("Get preset:", lms.get_preset()) 

    # 10) Set volume path
    save_path = "volume/output/lmstudio/test03/output_prompt.json"

    # 11) Generate (text completion/prompt)
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
    resp2 = lms.generate(prompt = prompt, save_path=save_path, timeout=500)
    print("\nAnswer2:")
    for k,v in resp2.items(): print(f"{k}: {v}")

    # Check if output was saved
    if not os.path.exists(save_path):
        raise FileNotFoundError(f"Output json file not found: {save_path}")

    # Open saved output
    with open(save_path, "r", encoding="utf-8") as f:
        json_output = json.load(f)

    print("Saved result:\n", json_output)

    # 12) Eject the model from ram when you’re done
    answ = lms.eject_model(model_id)
    print(answ)

    # Stop the server when you’re done
    answ = lms.stop_server()
    print(answ)