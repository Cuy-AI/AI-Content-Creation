import os
import json
import torchaudio as ta
import torch
from chatterbox.tts import ChatterboxTTS


class Chatterbox:

    def __init__(self, params_path: str ="tts/Chatterbox/params.json"):

        self.device = self._get_device()
        self.model = ChatterboxTTS.from_pretrained(device=self.device)

        self.params_path = params_path
        self.default_params = self._load_default_params(self.params_path)
        self.params = self.default_params


    def _load_default_params(self, params_path: str) -> dict:
        # Check if params file exist
        if not os.path.exists(params_path):
            raise FileNotFoundError(f"Params json file not found: {params_path}")

        # Open and save configurations
        with open(params_path, "r", encoding="utf-8") as f:
            default_params = json.load(f)
        
        return default_params


    def _get_device(self):
        # Automatically detect device
        if torch.cuda.is_available():
            return "cuda"
        else:
            raise EnvironmentError("No suitable device found. Please ensure you have a compatible GPU or CPU available.")
        
    
    def get_parameters(self) -> dict:
        # Return a copy of the current parameters
        return self.params.copy()

    def set_parameters(self, **kwargs):
        # For every parameter
        for key, value in kwargs.items():
            # Check if the parameter exists
            if key in self.params:
                # Check if the type is correct
                if isinstance(value, type(self.params[key])):
                    self.params[key] = value
                else:
                    raise TypeError(f"Expected type {type(self.params[key])} for parameter '{key}', got {type(value)}")
            else:
                raise KeyError(f"Unknown parameter '{key}' for model '{self.model_name}'")


    def generate(self, prompt, save_path=None):

        wav = self.model.generate(
            prompt, 
            **self.params
        )
        
        if save_path:
            ta.save(save_path, wav, self.model.sr)
        else:
            ta.save("tts/Chatterbox/output.wav", wav, self.model.sr)

        return {
            "prompt": prompt,
            **self.params
        }