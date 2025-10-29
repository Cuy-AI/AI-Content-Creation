import os
import json
import random
from components.LM.LMStudio.LMStudio import LMStudio

class ScriptGenerator_V1:

    def __init__(
        self, 
        # model_id = 'mistralai/magistral-small-2509', 
        model_id: str = 'mistralai/mistral-nemo-instruct-2407',
        preset: str = None
    ):
        self.lms = LMStudio(auto_start=False)
        self.active = False
        self.preset = preset
        self.model_id = model_id
        self.timeout = 240

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


    def get_script_schema(self, characters: list, images:list):
        return {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "A catchy YouTube reel video title under 60 characters"
                },
                "caption": {
                    "type": "string",
                    "description": "A short, intriguing description, like a YouTube video caption with multiple '#' included"
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
                                "description": (
                                    "A predefined character image that best fits the emotion or action being expressed in this scene. "
                                    "(e.g., angry, happy, surprised, explaining, confused). "
                                ),
                                "enum": images
                            },
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


    def get_script_messages(self, topic: str, category: str, summary: str, characters: list, images:list):

        # Parameters
        title_max_length = 60
        scene_number_range = (16, 20)

        return [
            {
                "role": "system",
                "content": 
                f"""
You are a creative scriptwriter for short-form educational videos featuring famous characters {characters}. 
You must strictly output JSON matching the following schema:

**Schema:**
{{
    "title": "string — a catchy YouTube reel video title under {title_max_length} characters",
    "caption": "string — a short, intriguing caption including at least one hashtag",
    "scenes": [
        {{
        "character": "{characters} — the speaker of the scene",
        "script": "What the character says in this scene",
        "character_image": "One of the predefined character images that best fits the emotion or action. Vary this image across scenes to match the tone (e.g., excited, confused, explaining).",
        }}
    ]
}}

**Instructions:**
- Make the script humorous in the style of {characters}, match their personalities.
- If characters tend to use dark humor, you can use it.
- Generate between {scene_number_range[0]} and {scene_number_range[1]} scenes total to keep the dialogue tight and engaging.
- Alternate characters, one must teach while the other reacts, asks questions.
- Include complete and informative real-world examples. 
- Make the script as if you were an human scriptwriter, not an AI. Don't add perfect sentences, add casual language.
- Explain the topic deeply but in a fun way. Don't use too much analogies.
- Your predefined character images will be: {images}
                """.strip()
            },
            {
                "role": "user",
                "content": 
                f"""
Generate the JSON for a short video based on this topic summary:

Topic: {topic}
Category: {category}
Summary: {summary}

Focus on explaining the concept while keeping it fun. 
End with a short, clever closing line. 
                """.strip()
            },
        ]


    def get_image_schema(self):
        return {
            "type": "object",
            "properties": {
                "important_scenes": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "scene_id": {
                                "type": "integer",
                                "description": "The ID of the scene that requires a web image"
                            },
                            "web_image": {
                                "type": "string",
                                "description": "A concise Google Images search query for an image that visually represents what is being talked about in this scene. Must realistically be found in Google Images."
                            }
                        }
                    }
                }
            }
        }

   
    def get_image_messages(self, script: dict, topic: str, category: str):
        return [
            {
                "role": "system",
                "content": f"""
You are given a JSON object representing a short animated script with multiple scenes.

Your task:
- Select about 25% of the most important or visually meaningful scenes — the ones that best explain a key concept or idea.
- Try sparcingly select scenes, avoid choosing consecutive scenes.
- For each selected scene, write one **realistic Google Images search query** that represents what is being *talked about* in the dialogue.
- The query must describe a **real, photographable or professionally illustrated concept**, not a fantasy or metaphor.
- MOST of the images must focus on the category - topic: {category} - {topic}.
- A small quantity of images (1 or 2 maximum) could be visuals related to the topic on a metaphorical way (e.g. When a character says "Complex interconected graph" -> Your query could be "Interconnected complex roads"). If you use this kind of metaphors ensure the image you describe is easy to find and not fictional.

Strict rules for the image query:
- Use only plain text describing what a person would actually search on Google Images.
- The query must look like a real search term (e.g. "software engineer optimizing neural network", "ford motor v8", "Beethoven original music partiture").

**DO NOT** INCLUDE:
- Characters/Objects of the script/scene doing/explaning things.
- File types (e.g. "GIF", "PNG", etc.)
- Parentheses, quotes, or explanations
- Abstract ideas, or commentary (e.g. “metaphorical”, “concept art”, etc.)
- Fictional or cartoon imagery.
- Unclear or subjective visuals.

Focus on:
- Real-world visuals that show the concept being discussed.
- Keep each query short (under 12 words) and specific.
- Vary queries, avoid repeating similar images.

Return a list of objects, each with:
- `scene_id`: the ID of the selected scene.
- `web_image`: the plain, realistic search query text.
                """.strip()
            },
            {
                "role": "user",
                "content": f"""
Here is the script JSON:
{json.dumps(script, indent=2)}
                """.strip()
            }
        ]


    def select_characters(self):
        # For now we are only using rick and morty. Future: select randomly?
        characters = [('Rick', 'Morty')]
        return random.choice(characters)
    
    
    def collect_images(self, characters: list, images_folder: str = 'volume/resources/LoreLabs/images/'):
        images = {}
        for character in characters:
            character_folder = images_folder + character.lower() + "/"
            if os.path.isdir(character_folder):
                for file in os.listdir(character_folder):
                    file_path = character_folder + file
                    if os.path.isfile(file_path): 
                        images[os.path.basename(file_path)] = file_path
        return images


    def generate_script(self, category: str, topic: str, summary: str, save_path:str = None):

        # Select characters
        characters = self.select_characters()

        # Collect images for characters
        images = self.collect_images(characters)

        # Prepare images, messages and schema
        fixed_images = list(images.keys())
        schema = self.get_script_schema(list(characters), fixed_images)
        messages = self.get_script_messages(topic, category, summary, list(characters), fixed_images)

        params = {}
        params["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": "qa_schema",
                "schema": schema,
                "strict": True
            }
        }

        # Generate script
        resp_script = self.lms.generate(messages = messages, parameters=params, timeout=self.timeout)
        resp_script = resp_script['output']

        # Rebuild images and fix scenes
        for idx, scene in enumerate(resp_script['scenes']):
            resp_script['scenes'][idx]['id'] = idx
            resp_script['scenes'][idx]['character_image'] = images.get(scene['character_image'], None)
            if resp_script['scenes'][idx]['character_image'] is None:
                print(f"[ERROR] Image {scene['character_image']} not found on images folder")

        
        # Generate image querys for each scene
        schema = self.get_image_schema()
        messages = self.get_image_messages(resp_script, topic, category)
        params["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": "qa_schema",
                "schema": schema,
                "strict": True
            }
        }

        resp_images = self.lms.generate(messages = messages, parameters=params, timeout=self.timeout)
        resp_images = resp_images['output']


        # Insert web images into the script
        important_scenes = resp_images.get('important_scenes', [])
        for imp_scene in important_scenes:
            scene_id = imp_scene['scene_id']
            web_image = imp_scene['web_image']

            if scene_id >= len(resp_script['scenes']):
                print(f"[ERROR] Scene ID {scene_id} is out of range for the script scenes")
                continue

            # Find the scene and insert the web_image
            for idx, scene in enumerate(resp_script['scenes']):
                if scene['id'] == scene_id:
                    resp_script['scenes'][idx]['web_image'] = web_image
                    break


        if save_path:
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(resp_script, f, indent=2, ensure_ascii=False)

        return resp_script


