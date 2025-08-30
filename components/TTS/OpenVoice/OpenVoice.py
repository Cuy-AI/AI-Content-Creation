import os
import json
import torch
from openvoice import se_extractor
from openvoice.api import ToneColorConverter
from melo.api import TTS


class OpenVoice:
    
    def __init__(self, params_path: str ="tts/OpenVoice/params.json"):

        self.params_path = params_path
        self.default_params = self._load_default_params(self.params_path)
        self.params = self.default_params

        self.device = self._get_device()
        self.ckpt_converter = 'tts/repos/OpenVoice/checkpoints_v2/converter'
        self.tone_color_converter = ToneColorConverter(f'{self.ckpt_converter}/config.json', device=self._get_device())
        self.tone_color_converter.load_ckpt(f'{self.ckpt_converter}/checkpoint.pth')

        # Reference
        # self.target_se, self.audio_name = se_extractor.get_se(reference_speaker, tone_color_converter, vad=True)

    def _get_device(self):
        # Automatically detect device
        if torch.cuda.is_available():
            return "cuda:0"
        else:
            raise EnvironmentError("No suitable device found. Please ensure you have a compatible GPU or CPU available.")

    def _load_default_params(self, params_path: str) -> dict:
        # Check if params file exist
        if not os.path.exists(params_path):
            raise FileNotFoundError(f"Params json file not found: {params_path}")

        # Open and save configurations
        with open(params_path, "r", encoding="utf-8") as f:
            default_params = json.load(f)
        
        return default_params
    

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


    def generate(self, prompt, save_path=None, save_temp=False):
        model = TTS(language=self.params["language"], device=self.device)

        target_se, audio_name = se_extractor.get_se(self.params["reference_speaker"], self.tone_color_converter, vad=True)
        
        speaker_ids = model.hps.data.spk2id
        print("speaker ids:", speaker_ids, "->", self.params["speaker_key"])
        speaker_id = speaker_ids[self.params["speaker_key"]]
        fixed_speaker_key = self.params["speaker_key"].lower().replace('_', '-')

        source_se = torch.load(f'tts/repos/OpenVoice/checkpoints_v2/base_speakers/ses/{fixed_speaker_key}.pth', map_location=self.device)
        if torch.backends.mps.is_available() and self.device == 'cpu':
            torch.backends.mps.is_available = lambda: False


        if save_path is None:
            save_path = f'tts/OpenVoice/output_v2_{fixed_speaker_key}.wav'
        
        save_path_without_file = os.path.dirname(save_path)
        temp_path = f'{save_path_without_file}/tmp.wav'

        model.tts_to_file(prompt, speaker_id, temp_path, speed=self.params["speed"])

        # Run the tone color converter
        encode_message = "@MyShell"
        self.tone_color_converter.convert(
            audio_src_path=temp_path, 
            src_se=source_se, 
            tgt_se=target_se, 
            output_path=save_path,
            message=encode_message)
        
        # Delete temp file
        if not save_temp:
            os.remove(temp_path)

        return {
            "prompt": prompt,
            **self.params
        }

