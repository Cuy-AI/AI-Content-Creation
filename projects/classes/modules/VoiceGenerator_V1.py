import os
from classes.ContainerManager import ContainerManager

class VoiceGenerator_V1:

    def __init__(self, resource_folder:str = None):
        # Create the OpenRouter container
        self.chatterbox_container = ContainerManager(image="chatterbox:latest", port=8002)
        self.chatterbox_client = None
        self.active = False
        self.resource_folder = resource_folder

    def start(self):
        if self.active: return
        self.chatterbox_container.start()
        self.chatterbox_client = self.chatterbox_container.create_client()
        self.chatterbox_client.set_params(
            temperature=0.85,
            exaggeration=0.6,
            cfg_weight=0.5,
        )
        self.active = True

    def stop(self):
        if not self.active: return
        self.chatterbox_container.stop()
        self.active = False


    def get_character_ref(self, character: str, lang_code: str):
        character = character.lower()
        path = os.path.join(self.resource_folder, f'{lang_code}/{character.lower()}.mp3')
        if not os.path.exists(path): raise ValueError(f"Couldn't find {character} voice reference {path}")
        return path
        

    def generate_voice(self, prompt: str, character: str, lang_code:str, save_file:str):
        
        character_voice = self.get_character_ref(character, lang_code)

        # Carefull with this
        save_file = save_file.replace("\\", "/")
        character_voice = character_voice.replace("\\", "/")

        self.chatterbox_client.set_params( audio_prompt_path = character_voice )
        return self.chatterbox_client.generate(prompt = prompt, save_path = save_file)['answer']

