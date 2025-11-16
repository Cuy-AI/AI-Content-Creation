import os
import json
import random
from classes.ContainerManager import ContainerManager

class ScriptGenerator_V2:

    def __init__(
        self, 
        model_name: str = "gpt-5-mini",
    ):
        self.openai_container = ContainerManager(image="openai:latest", port=8000, use_gpu = False)
        self.model_name = model_name
        self.active = False
        self.timeout = 240

    def start(self):
        if self.active: return
        self.openai_container.start()
        self.openai_client = self.openai_container.create_client()
        self.openai_client.set_model_name(model_name=self.model_name)
        self.active = True

    def stop(self):
        if not self.active: return
        self.openai_container.stop()
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
                                "enum": characters
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
                            "web_image": {
                                "type": "string",
                                "description": "A search query that will be used to download a realistic image from internet.",
                            }
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
            "required": ["scenes"]
        }


    def get_script_prompt(self, topic: str, category: str, knowledge_update: str, characters: list, images:list):

        # Parameters
        scene_number_range = (9, 13)
        words_per_sentence = (10, 30)

        return f"""
You are a master scriptwriter for ultra-addictive short educational videos starring characters {characters}. 
Your mission: produce JSON script that maximizes viewer retention to the highest possible level.

Your primary goal: 
CREATE A SCRIPT THAT MAKES VIEWERS UNABLE TO SCROLL AWAY.

JSON OUTPUT SCHEMA:
{{
"scenes": [
    {{
    "character": "One of: {characters}",
    "dialogue": "Medium-length dialogue with strong emotion, personality, tension, humor, and rising stakes.",
    "character_image": "One image from this predefined list: {images}",
    "web_image": "A SHORT, REALISTIC search query ONLY IF assigned (30% of scenes). Otherwise leave empty string."
    }}
]
}}

CRITICAL CREATIVE DIRECTIVES  

GENERAL DIALOGUE RULES:
- Dialogue MUST feel human, emotional, imperfect, reactive, and full of personality.
- Characters must talk like real people, like teenagers or young adults: interruptions, frustration, sarcasm, panic, excitement.
- NO emojis. NO sound effects. NO em dashes.
- Keep scenes MEDIUM length ({words_per_sentence[0]} to {words_per_sentence[1]} words): punchy but not too short, dense but not rambling.
- Alternate characters every scene.
- One character is the confused learner, the other is the expert.
- Avoid boring textbook tone. Avoid robotic explanations. Avoid 'perfectly composed sentences.'
- Use dark humor IF it fits the character.
- NO irrelevant tangents. Stay focused on the topic.
- Even while explaining, keep the emotional energy high.

THE 3-ACT RETENTION ARC

***ACT 1 - THE HOOK (Scene 1 only)***
This MUST be extremely sticky. Use psychological triggers like:
- 'You've been doing X wrong and it's messing everything up.'
- 'Nobody talks about this, but everyone should.'
- 'You think you understand X? You don't.'
- 'Here's the mistake that ruins everything.'
- 'If you're working with X, this should scare you.'

Rules:
- Don't reveal the answer.
- Create tension + confusion + urgency + emotional reaction.

***ACT 2 - PROGRESSION (Middle scenes)***
This is the rising tension.
- Reveal the truth slowly.
- On just a few scenes you can use micro-hooks like:
  * 'But that's not the crazy part.'
  * 'Here's where things get weird.'
  * 'And then it gets worse.'
  (Create your own hooks that best suit the dialog)

- The learner must occasionally panic, doubt, contradict, misunderstand, or freak out.
- The expert must show annoyance, sarcasm, superiority, frustration, or sudden bursts of excitement.
- Keep explanations technically correct, but emotionally charged and entertaining.
- Do NOT give the full answer too early.

***ACT 3 - CLIMAX (Final 1-2 scenes)***
This is the explosive payoff.
- Deliver the final truth, the hidden insight, the shocking reason, or the real mechanism behind the topic.
- Make it emotionally satisfying. A "holy crap" moment.
- The characters should react powerfully: either relief, shock, or revelation.
- After the final payoff, include one more scene to perform a short, clever, character-appropriate invitation to the viewers to follow us. The invitation must always use the word follow and must feel natural in the dialogue, not bolted on. The invitation could be related to the topic, the characters' personalities, or the final emotional tone of the scene.

WEB IMAGE GENERATION RULES
- Only 30 percent of scenes may include a web_image. Others MUST be an empty string.
- The query must be short, factual, and realistic.
- It must represent something physically findable online.
- Do NOT reference fictional characters, episodes, jokes, memes, or copyright content.
- NO impossible scenes. NO invented technology.
- Use objects, diagrams, dashboards, charts, real-world items, or well-known tech concepts.

TECHNICAL STRUCTURE RULES
- You must produce between {scene_number_range[0]} and {scene_number_range[1]} scenes.
- Each dialogue MUST move the topic forward or escalate emotion.
- Avoid long lectures. Break explanations into back-and-forth tension.
- Make the topic understandable for new students.
- Make sure that the dialogue between consecutive scenes is consistent.
- NO meta-comments or explanations. JUST the JSON.
- Being fun is mandatory. You must include jokes everywhere at the pure {characters} style.
- IMPORTANT: The script content will be based on your OWN KNOWLEDGE, but a Knowledge Update will be provided. This Knowledge Update should be used as a tool to help you improve the content of the script, but it is NOT the main focus of the script.

INPUT CONTEXT
Category: {category}
Topic: {topic}
Knowledge Update: {knowledge_update}
        """.strip()



    def select_characters(self):
        # For now we are only using rick and morty. Future: select randomly?
        characters = [['Rick', 'Morty']]
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


    def generate_script(self, category: str, topic: str, knowledge_update: str, save_path:str = None):

        # Select characters
        characters = self.select_characters()

        # Collect images for characters
        images = self.collect_images(characters)

        # Prepare images, messages and schema
        fixed_images = list(images.keys())
        schema = self.get_script_schema(list(characters), fixed_images)
        prompt = self.get_script_prompt(topic, category, knowledge_update, list(characters), fixed_images)

        self.openai_client.set_schema(schema=schema)

        # Generate script
        try:
            response = self.openai_client.generate(prompt=prompt, client_timeout=300)
            script = response['answer']['output']
            # print(f"Script:\n{script}")
        except Exception as e:
            print("[ERROR] LLM generation failed:", str(e))
            raise ValueError("LLM generation failed")

        # Try parse items
        if not isinstance(script, dict):
            print("[ERROR] LLM response is not a valid dictionary.")
            raise ValueError("LLM response is not a valid dictionary.")
        

        # Rebuild images and fix scenes
        for idx, scene in enumerate(script['scenes']):
            script['scenes'][idx]['id'] = idx
            script['scenes'][idx]['character_image'] = images.get(scene['character_image'], None)

            if script['scenes'][idx]['character_image'] is None:
                print(f"[ERROR] Image {scene['character_image']} not found on images folder")

            if script['scenes'][idx]['web_image'] == "": 
                script['scenes'][idx]['web_image'] = None

        

        return script


