import os
import json
from classes.ContainerManager import ContainerManager

class VoiceGenerator:

    def __init__(self):
        # Create the OpenRouter container
        self.chatterbox_container = ContainerManager(image="chatterbox:latest", port=8002)
        self.chatterbox_client = None
        self.active = False

    def start(self):
        if self.active: return
        self.chatterbox_container.start()
        self.chatterbox_client = self.chatterbox_container.create_client()
        self.chatterbox_client.set_params(
            temperature=0.7,
            exaggeration=0.5,
            cfg_weight=0.5,
        )
        self.active = True

    def stop(self):
        if not self.active: return
        self.chatterbox_container.stop()
        self.active = False

    def generate_voice(self, category: str, topic: str, scenes: list, save_folder: str):
        
        audios_paths = {
            'category': category,
            'topic': topic,
            'scenes': []
        }
        resources_folder = 'volume/resources/LoreLabs/voices/'
        for idx, scene in enumerate(scenes):

            character = scene['character'].lower()
            character_voice = resources_folder + character + '.mp3'
            
            self.chatterbox_client.set_params( audio_prompt_path = character_voice )

            scene_name = f'scene-{idx}'
            save_file = save_folder + scene_name + '.wav'
            result = self.chatterbox_client.generate(prompt = scene['script'], save_path = save_file)

            audios_paths['scenes'].append(result['answer']['save_path'])

        save_path = save_folder + 'metadata.json'
        with open(save_path, "w", encoding="utf-8") as f:
                json.dump(audios_paths, f, indent=2, ensure_ascii=False)



