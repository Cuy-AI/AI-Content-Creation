import os
import uvicorn

import torch
import whisper
import tempfile
from moviepy.editor import VideoFileClip

from classes.BaseAI import BaseAI
from classes.Server import Server


class WhisperAI(BaseAI):

    def __init__(self):
        """
        Initialize and load Whisper model.
        Whisper model size (tiny, base, small, medium, large).
        """

        super().__init__()
        
        self.valid_size = ["tiny", "base", "small", "medium", "large"]
        
        self._get_device()
        self.set_model_size("base")

        # self.params_path = "components/Editor/Whisper/params.json" # Host
        self.params_path = "params.json" # Docker
        self.set_default_params()


    def _get_device(self):
        if torch.cuda.is_available(): 
            self.device = "cuda"
            print(f"[INFO]: Successfully found cuda as device")
        else:
            self.device = "cpu"
            print(f"[WARN]: Using {self.device} as device")

    def set_model_size(self, model_size):
        if model_size not in self.valid_size: 
            raise ValueError(f"Model not found in models list: {model_size}")
        
        self.model_size = model_size
        self.model = whisper.load_model(model_size, device=self.device)
        return "Model size was loaded successfully"    
    
    def get_model_size(self):
        return self.model_size


    def generate(self, path):
        """
        Generate transcription from an audio or video file.
        Always returns a list of dicts with start, end, text.
        :param path: Path to audio or video file
        :return: [{"start": float, "end": float, "text": str}, ...]
        """
        input_path = path
        temp_audio = None

        # If it's a video, extract audio
        if path.lower().endswith((".mp4", ".mov", ".avi", ".mkv", ".webm")):
            video = VideoFileClip(path)
            temp_fd, temp_audio = tempfile.mkstemp(suffix=".wav")
            os.close(temp_fd)
            video.audio.write_audiofile(temp_audio, verbose=False, logger=None)
            input_path = temp_audio

        # Run Whisper
        result = self.model.transcribe(input_path, **self.params)

        # Clean up temp audio if created
        if temp_audio and os.path.exists(temp_audio):
            os.remove(temp_audio)

        # print("Raw result:", result)

        output = []
        if self.params["word_timestamps"]:
            for seg in result["segments"]:
                for w in seg.get("words", []):
                    output.append({
                        "start": float(w["start"]),
                        "end": float(w["end"]),
                        "text": w["word"].strip()
                    })
        else:
            for seg in result["segments"]:
                output.append({
                    "start": float(seg["start"]),
                    "end": float(seg["end"]),
                    "text": seg["text"].strip()
                })
        
        return output


    def merge_segments(self, word_segments, words_per_segment = None, max_duration = None, max_pause=None):
        """
        Merge word-level segments into larger segments.

        Args:
            word_segments: list of {"start": float, "end": float, "text": str}
            words_per_segment: if set, group by this many words per segment
            max_duration: if set, start a new segment after this many seconds
            max_pause: if set, start a new segment if speaker makes a pause for this many seconds

        Returns:
            List of merged segments with {"start", "end", "text"}
        """
        if not word_segments:
            return []

        merged = []
        buffer = []
        start_time = None

        for i in range(len(word_segments)):

            w = word_segments[i]

            if start_time is None: 
                start_time = w["start"]

            buffer.append(w)
            duration = w["end"] - start_time

            # Check if we should flush the buffer
            flush = False
            if words_per_segment and len(buffer) >= words_per_segment:
                flush = True
            if max_duration and duration >= max_duration:
                flush = True
            if max_pause and i+1 < len(word_segments) and (word_segments[i+1]["start"] - w["end"]) > max_pause:
                flush = True

            if flush:
                merged.append({
                    "start": buffer[0]["start"],
                    "end": buffer[-1]["end"],
                    "text": " ".join(x["text"] for x in buffer)
                })
                buffer = []
                start_time = None

        # Flush any leftovers
        if buffer:
            merged.append({
                "start": buffer[0]["start"],
                "end": buffer[-1]["end"],
                "text": " ".join(x["text"] for x in buffer)
            })

        return merged



if __name__ == "__main__":
    chatterbox_server = Server(ai_class=WhisperAI)
    app = chatterbox_server.app
    uvicorn.run(app, host="0.0.0.0", port=8001)