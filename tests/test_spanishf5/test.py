import os
import json
from classes.ContainerManager import ContainerManager


def test_spanishf5():
    
    # Create the SpanishF5 container
    spanishf5_container = ContainerManager(image="spanishf5:latest", port=8004)
    spanishf5_container.start()

    # Create the SpanishF5 component
    spanishf5_client = spanishf5_container.create_client()

    output_folder = spanishf5_container.volume_path + "/output/spanishf5/test01/"
    resources_folder = spanishf5_container.volume_path + "/resources/audios/test/"

    # Dina voice ---------------------------
    spanishf5_client.set_params(
        ref_audio=resources_folder + "dina.mp3",
        remove_silence=False
    )

    output_path = output_folder + "output_dina.wav"
    result = spanishf5_client.generate(
        prompt="Mira causa, la historia nos enseña que el comunismo, aunque suene bonito en el papel, en la práctica no funciona. Promete igualdad, pero al final termina siendo lo mismo de siempre: unos pocos con el poder y el pueblo haciendo cola para conseguir lo básico. En el Perú ya hemos visto cómo esas ideas radicales trajeron más violencia que progreso. No se trata solo de ideología, sino de entender que la gente quiere chamba, oportunidades y estabilidad, no discursos vacíos que al final dejan al país en la ruina.", 
        save_path=output_path 
    )

    print("Path exists:", os.path.exists(output_path))
    print("Successfully generated audio with parameters:\n", json.dumps(result, indent=4))

    # Fujimori voice ---------------------------
    spanishf5_client.set_params(
        ref_audio=resources_folder + "fujimori.mp3"
    )

    output_path = output_folder + "output_fujimori.wav"
    result = spanishf5_client.generate(
        prompt="Mira causa, la historia nos enseña que el comunismo, aunque suene bonito en el papel, en la práctica no funciona. Promete igualdad, pero al final termina siendo lo mismo de siempre: unos pocos con el poder y el pueblo haciendo cola para conseguir lo básico. En el Perú ya hemos visto cómo esas ideas radicales trajeron más violencia que progreso. No se trata solo de ideología, sino de entender que la gente quiere chamba, oportunidades y estabilidad, no discursos vacíos que al final dejan al país en la ruina.", 
        save_path=output_path
    )

    print("Path exists:", os.path.exists(output_path))
    print("Successfully generated audio with parameters:\n", json.dumps(result, indent=4))

    # Stop container
    spanishf5_container.stop()