# from components.MediaAnalyzer.Clip.Clip import Clip
from classes.ContainerManager import ContainerManager

def test_clip():
    # Initialize the class
    # clip = Clip()

    clip_container = ContainerManager(image="clip:latest", port=8005, use_gpu = True)
    clip_container.start()
    clip = clip_container.create_client()


    # Test 1 ------------------------------------------------------------------------------------
    print("Test 1 - Single Image")

    # Define labels and image path
    candidate_labels = ["friends", "dogs", "persons", "alcohol", "water", "something else"]
    image_file = "volume/resources/images/comfyui/pic.png"

    # Run inference
    predictions = clip.predict(
        image_path=image_file, 
        labels=candidate_labels
    )['answer']

    # Print the most likely result
    best_match = max(predictions, key=predictions.get)
    print(f"Top prediction: {best_match} ({predictions[best_match]:.2%})")
    print(predictions)


    # Test 2 ------------------------------------------------------------------------------------
    print("Test 2 - Single frame of a video")
    predictions = clip.predict_video_frame(
        video_path="volume/resources/videos/test/test01.mp4",
        labels=["a person walking", "a car driving", "an empty street"],
        timestamp_seconds=45.5
    )['answer']

    top_choice = max(predictions["predictions"], key=predictions["predictions"].get)
    print(f"At {predictions['timestamp_s']}s, the model sees: {top_choice}")
    print(predictions)

    
    # Test 3 ------------------------------------------------------------------------------------
    print("Test 3 - Multiple video frames (intervals)")
    predictions = clip.predict_video_intervals(
        video_path="volume/resources/videos/test/test01.mp4",
        labels=["a person walking", "a car driving", "an empty street"],
        interval_seconds=10.0
    )['answer']

    print("Predictions:")
    print(predictions)