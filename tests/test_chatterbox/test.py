import json
from tts.Chatterbox.Chatterbox import Chatterbox

def test_chatterbox():
    
    model = Chatterbox()

    model.set_parameters(
        temperature=0.8,
        exaggeration=0.5,
        cfg_weight=0.5,
        audio_prompt_path="tts/voices/cartoon_girl.mp3"
    )

    result = model.generate(
        "Alex hit 'Enter.' The counter-code rippled through the network, unraveling the hidden surveillance web. Screens flashed red, logs deleted, and for the first time, the truth was no longer locked inside a server. The world woke up to the shadows that had watched it for years. The conspiracy was exposed, and a new era of transparency began, all sparked by a young coder's curiosity.", 
        save_path="testing/test_chatterbox/output.wav"
    )

    print("Successfully generated audio with parameters:\n", json.dumps(result, indent=4))
