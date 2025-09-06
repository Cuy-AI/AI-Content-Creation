import os
import json
import uvicorn

import torch
import torchaudio as ta
from chatterbox.tts import ChatterboxTTS

from classes.BaseAI import BaseAI
from classes.Server import Server

class Chatterbox(BaseAI):

    def __init__(self):

        super().__init__()

        self.device = self._get_device()
        self.model = ChatterboxTTS.from_pretrained(device=self.device)
        # self.params_path = "components/TTS/Chatterbox/params.json" # Host
        self.params_path = "params.json" # Docker
        self.set_default_params()


    def _get_device(self):
        # Automatically detect device
        if torch.cuda.is_available():
            print(f"[INFO]: Successfully found cuda as device")
            return "cuda"
        if torch.backends.mps.is_available():
            device = "mps"
        else:
            device = "cpu"

        print(f"[WARN]: Using {device} as device")
        # raise EnvironmentError(f"No GPU device found. Please ensure you have a compatible GPU available.")
        return device
        

    def generate(self, prompt: str, save_path: str|None = None):

        wav = self.model.generate(
            prompt,
            **self.params
        )
        
        if save_path:
            # If save_path looks like a file (has an extension), handle as file
            if os.path.splitext(save_path)[1]:  
                if os.path.dirname(save_path) != '':
                    os.makedirs(os.path.dirname(save_path), exist_ok=True)  # ensure parent dir exists
                ta.save(save_path, wav, self.model.sr)
            else:
                # treat as directory -> auto-generate a filename
                if os.path.dirname(save_path) != '':
                    os.makedirs(save_path, exist_ok=True)
                save_path = os.path.join(save_path, "output.wav")
                ta.save(save_path, wav, self.model.sr)

        return {
            "prompt": prompt,
            "save_path": save_path,
            **self.params
        }


if __name__ == "__main__":
    chatterbox_server = Server(ai_class=Chatterbox)
    app = chatterbox_server.app
    uvicorn.run(app, host="0.0.0.0", port=8002)