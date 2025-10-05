import os
import json
from components.LM.LMStudio.LMStudio import LMStudio

class ScriptGenerator:

    def __init__(self, model_id = 'mistralai/magistral-small-2509', preset='@local:w1-script-generator-magistral-v1'):
        self.lms = LMStudio(auto_start=False)
        self.active = False
        self.preset = preset
        self.model_id = model_id

    def start(self):
        if self.active: return
        self.lms.start_server()
        self.lms.set_preset(preset_identifier=self.preset)
        self.lms.load_model(self.model_id, config={"contextLength": 8192})
        self.active = True

    def stop(self):
        if not self.active: return
        self.lms.eject_model(self.model_id)
        self.lms.stop_server()
        self.active = False

    def generate_script(self, summary, save_path = None):
        
        # For now we are only using rick and morty. Future: select randomly?
        characters = ('Rick', 'Morty')

        # Collect images for characters
        images = []
        images_folder = 'volume/resources/LoreLabs/images/'
        for character in characters:
            character_folder = images_folder + character.lower() + "/"
            if os.path.isdir(character_folder):
                for file in os.listdir(character_folder):
                    file_path = character_folder + file
                    if os.path.isfile(file_path): images.append(file_path)

        schema = {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "A catchy YouTube reel video title under 60 characters"
                },
                "caption": {
                    "type": "string",
                    "description": "A short, intriguing description, like a YouTube video caption with '#' included"
                },
                "scenes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                        "character": {
                            "type": "string",
                            "description": "The name of the character that is speaking during the scene",
                            "enum": list(characters)
                        },
                        "script": {
                            "type": "string",
                            "description": "What is being said by the character"
                        },
                        "character_image": {
                            "type": "string",
                            "description": "One of the predefined character images that best fits the emotion or action. Vary this image across scenes to match the tone (e.g., excited, confused, explaining). Don't reuse the same image for every scene.",
                            "enum": [os.path.basename(img) for img in images]
                        },
                        "web_image": {
                            "type": "string",
                            "description": "A query for searching on internet an image about what is being talked about during the scene"
                        }
                        },
                        "required": [
                            "character",
                            "script",
                            "character_image",
                            "web_image"
                        ]
                    }
                }
            },
            "required": [
                "title",
                "caption",
                "scenes"
            ]
        }

        messages = [
            {
                "role": "system",
                "content": 
                f"""
You are a creative scriptwriter for short-form educational videos featuring famous characters {characters}. 
You must strictly output JSON matching the following schema:

{{
    "title": "string — a catchy YouTube reel video title under 60 characters",
    "caption": "string — a short, intriguing caption including at least one hashtag",
    "scenes": [
        {{
        "character": "{characters} — the speaker of the scene",
        "script": "What the character says in this scene",
        "character_image": "One of the predefined character images that best fits the emotion or action. Vary this image across scenes to match the tone (e.g., excited, confused, explaining). Don't reuse the same image for every scene.",
        "web_image": "A concise Google Images search query for an image that visually represents what is being talked about in this scene"
        }}
    ]
}}

Make the script natural, dynamic, and humorous in the style of {characters}, but still educational and accurate.
Each scene should have 2-5 sentences maximum, alternating between {characters} for an engaging dialogue.
Include brief, insightful explanations or relatable real-world examples. 
Keep humor, but ensure each key concept is explained clearly enough for a beginner to understand.
                """.strip()
            },
            {
                "role": "user",
                "content": 
                f"""
Generate the JSON for a short video based on this topic summary:

Topic: {summary['topic']}
Category: {summary['category']}
Summary: {summary['summary']}

Focus on clearly explaining the concept while keeping it fun and conversational. 
End with a short, clever closing line. 
Ensure that every key from the schema is filled properly.
Try including one or two real-world examples where appropriate. (Optionally)
Generate between 10 and 14 scenes total to keep the dialogue tight and engaging.
                """.strip()
            },
        ]

        params = {}
        params["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": "qa_schema",
                "schema": schema,
                "strict": True
            }
        }

        # print("Schema:")
        # print(schema)

        resp = self.lms.generate(messages = messages, parameters=params, timeout=180)
        resp = resp['output']

        # Rebuild images
        for idx, scene in enumerate(resp['scenes']):
            img_filename = scene['character_image']
            changed = False
            for full_path_img in images:
                if img_filename in full_path_img:
                    resp['scenes'][idx]['character_image'] = full_path_img
                    changed = True
                    break
            if not changed: print(f"[ERROR] Image {img_filename} not found on images folder")

        if save_path:
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(resp, f, indent=2, ensure_ascii=False)

        return resp




