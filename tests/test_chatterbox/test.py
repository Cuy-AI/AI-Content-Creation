import os
import json
from classes.ContainerManager import ContainerManager
from classes.Component import Component
from components.TTS.Chatterbox.Chatterbox import Chatterbox


def test_chatterbox():
    
    # Create the OpenRouter container
    chatterbox_container = ContainerManager(image="chatterbox:latest", port=8002)
    chatterbox_container.start()

    # Create the OpenRouter component
    chatb = Component(ai_class=Chatterbox, port=8002)

    test_folder = "output/chatterbox/test02/"
    resources_folder = "resources/voices/"

    output_host = chatterbox_container.host_volume + '/' + test_folder
    output_container = chatterbox_container.container_volume + '/' + test_folder

    resources_container = chatterbox_container.container_volume + '/' + resources_folder

    # Cartoon voice ---------------------------
    chatb.set_params(
        temperature=0.8,
        exaggeration=0.5,
        cfg_weight=0.5,
        audio_prompt_path= resources_container + "cartoon_girl.mp3"
    )

    result = chatb.generate(
        prompt="Alex hit 'Enter.' The counter-code rippled through the network, unraveling the hidden surveillance web. Screens flashed red, logs deleted, and for the first time, the truth was no longer locked inside a server. The world woke up to the shadows that had watched it for years. The conspiracy was exposed, and a new era of transparency began, all sparked by a young coder's curiosity.", 
        save_path= output_container + "output_cartoon_girl.wav"
    )

    print("Path exists:", os.path.exists( output_host + "output_cartoon_girl.wav"))
    print("Successfully generated audio with parameters:\n", json.dumps(result, indent=4))

    # Deep voice ---------------------------
    chatb.set_params(
        audio_prompt_path= resources_container + "deep_voice.wav"
    )

    result = chatb.generate(
        prompt="Alex hit 'Enter.' The counter-code rippled through the network, unraveling the hidden surveillance web. Screens flashed red, logs deleted, and for the first time, the truth was no longer locked inside a server. The world woke up to the shadows that had watched it for years. The conspiracy was exposed, and a new era of transparency began, all sparked by a young coder's curiosity.", 
        save_path= output_container + "output_deep_voice.wav"
    )

    print("Path exists:", os.path.exists( output_host + "deep_voice.wav"))
    print("Successfully generated audio with parameters:\n", json.dumps(result, indent=4))

    # Homer voice ---------------------------
    chatb.set_params(
        audio_prompt_path= resources_container + "homer_simpson.mp3"
    )

    result = chatb.generate(
        prompt="Alex hit 'Enter.' The counter-code rippled through the network, unraveling the hidden surveillance web. Screens flashed red, logs deleted, and for the first time, the truth was no longer locked inside a server. The world woke up to the shadows that had watched it for years. The conspiracy was exposed, and a new era of transparency began, all sparked by a young coder's curiosity.", 
        save_path= output_container + "output_homer_simpson.wav"
    )

    print("Path exists:", os.path.exists( output_host + "homer_simpson.wav"))
    print("Successfully generated audio with parameters:\n", json.dumps(result, indent=4))

    # Puss in boots voice ---------------------------
    chatb.set_params(
        audio_prompt_path= resources_container + "puss_in_boots.mp3"
    )

    result = chatb.generate(
        prompt="Alex hit 'Enter.' The counter-code rippled through the network, unraveling the hidden surveillance web. Screens flashed red, logs deleted, and for the first time, the truth was no longer locked inside a server. The world woke up to the shadows that had watched it for years. The conspiracy was exposed, and a new era of transparency began, all sparked by a young coder's curiosity.", 
        save_path= output_container + "output_puss_in_boots.wav"
    )

    print("Path exists:", os.path.exists( output_host + "puss_in_boots.wav"))
    print("Successfully generated audio with parameters:\n", json.dumps(result, indent=4))


    # Stop container
    chatterbox_container.stop()
