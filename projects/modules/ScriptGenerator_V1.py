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
                            "dialogue": {
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
                            "dialogue",
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
        scene_number_range = (13, 15)

        return [
            {
                "role": "system",
                "content": 
                f"""
You are a creative scriptwriter for short-form educational videos featuring famous characters {characters}. 
You must strictly output JSON matching the following schema:
{{
    "scenes": [
        {{
        "character": "{characters} — the speaker of the scene",
        "dialogue": "What the character says in this scene",
        "character_image": "One of the predefined character images that best fits the emotion or action. Vary this image across scenes to match the tone (e.g., excited, confused, explaining).",
        }}
    ]
}}

Instructions:
- Make the dialogue humorous in the style of {characters}, match their personalities. If characters tend to use dark humor, you can use it.
- Generate between {scene_number_range[0]} and {scene_number_range[1]} scenes total.
- Alternate characters, one or more (learners) has a problem/situation/question related to the a given topic and the other will give a smart solution while deeply explains the topic.
- Make the dialogue as if you were an human scriptwriter, not an AI. Don't use repetitive or perfect sentences, add casual language like if you were a teenager.
- Focus only on explaining the topic deeply. You and the characters are experts, don't waste time with silly analogies.
- You are forbidden to generate emojis, or non word sounds or the em dash symbol (—).
- Always remain focus on explaining the topic and solve the situation. Don't go off on tangents.
- It's mandatory to finish the dialog with a BRIEF "Follow us for more educational videos" phrase.
- Your predefined character_images will be: {images}
                """.strip()
            },
            {
                "role": "user",
                "content": 
                f"""
Generate the script for a short video based on this topic summary:
Category: {category}
Topic: {topic}
Summary: {summary}
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
Analyze the provided JSON script, which contains a dialogue explaining a technical topic. Your task is to generate a list of concise, effective image search queries for 30% of the total scenes. The goal is to find visual representations that perfectly fit the dialogue's content or its primary analogy.
Try not to select consecutive scenes. Keep the images spread out across all scenes. 

Output Format: The output must be a JSON list of objects, where each object contains the id of the scene and the generated query.
[
    {{"id": "<Scene ID>", "query": "<Generated Search Query>"}},
    // ... (Repeat for up to 25% of scenes)
]

Query Content (Critical):

- Queries must be designed to retrieve real-world images, stock photos, or simple technical graphics.

- Forbidden: Do not generate queries for artistic, abstract, cartoon, fictional, or highly conceptual subjects. You are also forbidden to generate images that include the scene characters doing /using stuff because this is also fictional and will not be easy to find.

- Focus on the literal technical concept or the literal object used in the analogy. Querys must be SHORT and SIMPLE

Query Quality: Each query must be specific and high-signal to ensure the first search result is high-quality and directly relevant to the line of dialogue. Assume the query will be executed by an automated system that selects the first image found.

Language: Generate queries in the same language as the primary technical terms in the script (English).
                """.strip()
            },
            {
                "role": "user",
                "content": f"""
The JSON script:
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


