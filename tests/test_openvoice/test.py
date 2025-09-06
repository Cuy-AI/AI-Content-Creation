import os
import json
from classes.ContainerManager import ContainerManager


def test_openvoice():

    openvoice_container = ContainerManager(image="openvoice:latest", port=8003, use_gpu = True)
    openvoice_container.start()

    # Create the openvoice client
    openVoice_client = openvoice_container.create_client()
    
    test_folder = 'test01'

    test_folder = "output/openvoice/test02/"
    resources_folder = "resources/voices/"

    output_host = openvoice_container.host_volume + '/' + test_folder
    output_container = openvoice_container.container_volume + '/' + test_folder

    resources_container = openvoice_container.container_volume + '/' + resources_folder

    # English testing
    openVoice_client.set_params(
        language= "EN_NEWEST",
        reference_speaker= resources_container + "homer_simpson.mp3",
        speaker_key= "EN-Newest",
        speed= 0.8
    )

    result = openVoice_client.generate(
        prompt="Alex hit 'Enter.' The counter-code rippled through the network, unraveling the hidden surveillance web. Screens flashed red, logs deleted, and for the first time, the truth was no longer locked inside a server. The world woke up to the shadows that had watched it for years. The conspiracy was exposed, and a new era of transparency began, all sparked by a young coder's curiosity.", 
        save_path= output_container + "output_en_homer_simpson.wav"
    )

    print("Path exists:", os.path.exists( output_host + "output_en_homer_simpson.wav"))
    print("Successfully generated audio with parameters:\n", json.dumps(result, indent=4))


    openVoice_client.set_params(
        language= "EN_NEWEST",
        reference_speaker= resources_container + "cartoon_girl.mp3",
        speaker_key= "EN-Newest",
        speed= 0.8
    )

    result = openVoice_client.generate(
        prompt="Alex hit 'Enter.' The counter-code rippled through the network, unraveling the hidden surveillance web. Screens flashed red, logs deleted, and for the first time, the truth was no longer locked inside a server. The world woke up to the shadows that had watched it for years. The conspiracy was exposed, and a new era of transparency began, all sparked by a young coder's curiosity.", 
        save_path= output_container + "output_en_cartoon_girl.wav"
    )

    print("Path exists:", os.path.exists( output_host + "output_en_cartoon_girl.wav"))
    print("Successfully generated audio with parameters:\n", json.dumps(result, indent=4))


    # Spanish testing
    openVoice_client.set_params(
        language= "ES",
        reference_speaker= resources_container + "carnal_mexico.mp3",
        speaker_key= "ES",
        speed= 0.8
    )

    result = openVoice_client.generate(
        prompt="Alex pulsó 'Enter'. El contracódigo se propagó por la red, desenredando la red de vigilancia oculta. Las pantallas parpadearon en rojo, los registros se borraron y, por primera vez, la verdad ya no estaba encerrada en un servidor. El mundo despertó ante las sombras que lo habían vigilado durante años. La conspiración fue expuesta y comenzó una nueva era de transparencia, todo ello impulsado por la curiosidad de un joven programador.", 
        save_path= output_container + "output_es_carnal_mexico.wav"
    )

    print("Path exists:", os.path.exists( output_host + "output_es_carnal_mexico.wav"))
    print("Successfully generated audio with parameters:\n", json.dumps(result, indent=4))

    openvoice_container.stop()


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