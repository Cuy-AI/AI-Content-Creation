import os
import json
from classes.ContainerManager import ContainerManager

def test_whisper():

    whisper_container = ContainerManager(image="whisper:latest", port=8001, use_gpu = True)
    whisper_container.start()

    whisperer = whisper_container.create_client()

    answ = whisperer.set_model_size(
        model_size="medium", 
        client_timeout = 90 # Set a custom timeout 
    )
    print("Set model size answer:", answ)

    # Optional config
    whisperer.set_params(language="en", task="transcribe", word_timestamps=True)

    # Transcribe a video (Single word as segment)
    input_video = whisper_container.volume_path + "/resources/videos/test/test01.mp4"
    subs = whisperer.generate(path=input_video)
    print("Video:")
    for sub in subs['answer']: print(sub)
    
    
    # Fix segments (You must use this method with Single word as segment)
    fixed_subs = whisperer.merge_segments(word_segments=subs['answer'], words_per_segment=4, max_duration=1.5)
    print("\nFixed subs:")
    for sub in fixed_subs['answer']: print(sub)

    # Transcribe an audio (Sentences as segments)
    input_audio = whisper_container.volume_path + "/resources/audios/test/test01.mp3"
    whisperer.set_params(word_timestamps=False)
    subs2 = whisperer.generate(path=input_audio)
    print("\nAudio:")
    for sub in subs2["answer"]: print(sub)

    # whisper_container.stop()


# [
#   {"start": 0.5, "end": 2.1, "text": "Hello world"},
#   {"start": 2.2, "end": 4.0, "text": "This is a test"}
# ]
