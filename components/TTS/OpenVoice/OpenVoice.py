import os
import json
import uvicorn

import torch
from openvoice import se_extractor
from openvoice.api import ToneColorConverter
from melo.api import TTS

from classes.Server import Server
from classes.BaseAI import BaseAI


class OpenVoice(BaseAI):
    
    def __init__(self):

        super().__init__()

        # self.params_path = "components/TTS/OpenVoice/params.json" # Host
        self.params_path = "params.json" # Docker
        self.set_default_params()

        self.device = self._get_device()
        # self.ckpt_converter = '../Repos/OpenVoice/checkpoints_v2/converter' # Host
        self.ckpt_converter = '/tmp/OpenVoice/checkpoints_v2/converter' # Docker
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

    def generate(self, prompt, save_path = None, save_temp = False):
        model = TTS(language=self.params["language"], device=self.device)

        target_se, audio_name = se_extractor.get_se(self.params["reference_speaker"], self.tone_color_converter, vad=True)
        
        speaker_ids = model.hps.data.spk2id
        print("speaker ids:", speaker_ids, "->", self.params["speaker_key"])
        speaker_id = speaker_ids[self.params["speaker_key"]]
        fixed_speaker_key = self.params["speaker_key"].lower().replace('_', '-')

        # source_se = torch.load(f'../Repos/OpenVoice/checkpoints_v2/base_speakers/ses/{fixed_speaker_key}.pth', map_location=self.device) # Host
        source_se = torch.load(f'/tmp/OpenVoice/checkpoints_v2/base_speakers/ses/{fixed_speaker_key}.pth', map_location=self.device) # Docker
        if torch.backends.mps.is_available() and self.device == 'cpu':
            torch.backends.mps.is_available = lambda: False


        if save_path is None:
            save_path = f'volume/output/openvoice/default_output/output_v2_{fixed_speaker_key}.wav'


        # If save_path looks like a file (has an extension), handle as file
        if os.path.splitext(save_path)[1]:  
            dir_name = os.path.dirname(save_path)
            if dir_name != '':
                os.makedirs(dir_name, exist_ok=True)  # ensure parent dir exists
            temp_path = f'{dir_name}/tmp.wav'
            model.tts_to_file(prompt, speaker_id, temp_path, speed=self.params["speed"])
        else:
            # treat as directory -> auto-generate a filename
            if os.path.dirname(save_path) != '':
                os.makedirs(save_path, exist_ok=True)
            save_path = os.path.join(save_path, f"output_v2_{fixed_speaker_key}.wav")
            temp_path = os.path.join(save_path, "tmp.wav")
            model.tts_to_file(prompt, speaker_id, temp_path, speed=self.params["speed"])
            
        
        # save_path_without_file = os.path.dirname(save_path)
        # temp_path = f'{save_path_without_file}/tmp.wav'

        # model.tts_to_file(prompt, speaker_id, temp_path, speed=self.params["speed"])

        # Run the tone color converter
        encode_message = "@MyShell"
        self.tone_color_converter.convert(
            audio_src_path=temp_path, 
            src_se=source_se, 
            tgt_se=target_se, 
            output_path=save_path,
            message=encode_message
        )
        
        # Delete temp file
        if not save_temp:
            os.remove(temp_path)

        return {
            "prompt": prompt,
            **self.params
        }

if __name__ == "__main__":
    openvoice_server = Server(ai_class=OpenVoice)
    app = openvoice_server.app
    uvicorn.run(app, host="0.0.0.0", port=8003)


"""
With language: EN_NEWEST
Speaker keys: {'EN-Newest': 0}

With language: EN
Speaker keys: {'EN-US': 0, 'EN-BR': 1, 'EN_INDIA': 2, 'EN-AU': 3, 'EN-Default': 4}

With language: ES
Speaker keys: {'ES': 0}

With language: FR
Speaker keys: {'FR': 0}

With language: ZH
Speaker keys: {'ZH': 1}

With language: JP
Speaker keys: {'JP': 0}

With language: KR
Speaker keys: {'KR': 0}
"""