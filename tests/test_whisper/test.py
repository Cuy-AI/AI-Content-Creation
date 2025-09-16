import os
import json
from classes.ContainerManager import ContainerManager


def test_whisper():

    whisper_container = ContainerManager(image="whisper:latest", port=8001, use_gpu = True)
    whisper_container.start()

    whisperer = whisper_container.create_client()

    whisperer.set_model_size(model_size="base")

    # Optional config
    whisperer.set_params(language="en", task="transcribe")

    # Transcribe a video
    subs = whisperer.generate(path="/app/volume/resources/videos/test/test01.mp4")
    print("Video:\n", subs)

    # Transcribe an audio
    subs2 = whisperer.generate(path="/app/volume/resources/audios/test/test01.mp3")
    print("Audio:\n", subs2)


# [
#   {"start": 0.5, "end": 2.1, "text": "Hello world"},
#   {"start": 2.2, "end": 4.0, "text": "This is a test"}
# ]
