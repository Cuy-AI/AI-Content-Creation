import json
from tts.OpenVoice.OpenVoice import OpenVoice


def test_openvoice():
    
    model = OpenVoice()

    # English testing
    model.set_parameters(
        language= "EN_NEWEST",
        reference_speaker= "tts/voices/homer_simpson.mp3",
        speaker_key= "EN-Newest",
        speed= 0.8
    )

    result = model.generate(
        "Alex hit 'Enter.' The counter-code rippled through the network, unraveling the hidden surveillance web. Screens flashed red, logs deleted, and for the first time, the truth was no longer locked inside a server. The world woke up to the shadows that had watched it for years. The conspiracy was exposed, and a new era of transparency began, all sparked by a young coder's curiosity.", 
        save_path="testing/test_openvoice/output_en.wav"
    )

    print("Successfully generated audio with parameters:\n", json.dumps(result, indent=4))


    # Spanish testing
    model.set_parameters(
        language= "ES",
        reference_speaker= "tts/voices/carnal_mexico.mp3",
        speaker_key= "ES",
        speed= 0.8
    )

    result = model.generate(
        "Alex pulsó 'Enter'. El contracódigo se propagó por la red, desenredando la red de vigilancia oculta. Las pantallas parpadearon en rojo, los registros se borraron y, por primera vez, la verdad ya no estaba encerrada en un servidor. El mundo despertó ante las sombras que lo habían vigilado durante años. La conspiración fue expuesta y comenzó una nueva era de transparencia, todo ello impulsado por la curiosidad de un joven programador.", 
        save_path="testing/test_openvoice/output_es.wav"
    )

    print("Successfully generated audio with parameters:\n", json.dumps(result, indent=4))


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