import os
import json
from classes.ContainerManager import ContainerManager


def test_chatterbox():
    
    # Create the OpenRouter container
    chatterbox_container = ContainerManager(image="chatterbox:latest", port=8002)
    chatterbox_container.start()

    # Create the OpenRouter component
    chatterbox_client = chatterbox_container.create_client()

    output_folder = chatterbox_container.volume_path  + "/output/chatterbox/test02/"
    resources_folder = chatterbox_container.volume_path  + "/resources/voices/"

    # Cartoon voice ---------------------------
    chatterbox_client.set_params(
        temperature=0.8,
        exaggeration=0.5,
        cfg_weight=0.5,
        audio_prompt_path= resources_folder + "cartoon_girl.mp3"
    )

    output_path = output_folder + "output_cartoon_girl.wav"
    result = chatterbox_client.generate(
        prompt="Alex hit 'Enter.' The counter-code rippled through the network, unraveling the hidden surveillance web. Screens flashed red, logs deleted, and for the first time, the truth was no longer locked inside a server. The world woke up to the shadows that had watched it for years. The conspiracy was exposed, and a new era of transparency began, all sparked by a young coder's curiosity.", 
        save_path= output_path 
    )

    print("Path exists:", os.path.exists( output_path ))
    print("Successfully generated audio with parameters:\n", json.dumps(result, indent=4))

    # Deep voice ---------------------------
    chatterbox_client.set_params(
        audio_prompt_path= resources_folder + "deep_voice.wav"
    )

    output_path = output_folder + "output_deep_voice.wav"
    result = chatterbox_client.generate(
        prompt="Alex hit 'Enter.' The counter-code rippled through the network, unraveling the hidden surveillance web. Screens flashed red, logs deleted, and for the first time, the truth was no longer locked inside a server. The world woke up to the shadows that had watched it for years. The conspiracy was exposed, and a new era of transparency began, all sparked by a young coder's curiosity.", 
        save_path= output_path
    )

    print("Path exists:", os.path.exists( output_path ))
    print("Successfully generated audio with parameters:\n", json.dumps(result, indent=4))

    # Homer voice ---------------------------
    chatterbox_client.set_params(
        audio_prompt_path= resources_folder + "homer_simpson.mp3"
    )

    output_path = output_folder + "output_homer_simpson.wav"
    result = chatterbox_client.generate(
        prompt="Alex hit 'Enter.' The counter-code rippled through the network, unraveling the hidden surveillance web. Screens flashed red, logs deleted, and for the first time, the truth was no longer locked inside a server. The world woke up to the shadows that had watched it for years. The conspiracy was exposed, and a new era of transparency began, all sparked by a young coder's curiosity.", 
        save_path= output_path
    )

    print("Path exists:", os.path.exists(output_path))
    print("Successfully generated audio with parameters:\n", json.dumps(result, indent=4))

    # Puss in boots voice ---------------------------
    chatterbox_client.set_params(
        audio_prompt_path= resources_folder + "puss_in_boots.mp3"
    )

    output_path = output_folder + "output_puss_in_boots.wav"
    result = chatterbox_client.generate(
        prompt="Alex hit 'Enter.' The counter-code rippled through the network, unraveling the hidden surveillance web. Screens flashed red, logs deleted, and for the first time, the truth was no longer locked inside a server. The world woke up to the shadows that had watched it for years. The conspiracy was exposed, and a new era of transparency began, all sparked by a young coder's curiosity.", 
        save_path= output_path
    )

    print("Path exists:", os.path.exists(output_path))
    print("Successfully generated audio with parameters:\n", json.dumps(result, indent=4))


    # Stop container
    chatterbox_container.stop()
