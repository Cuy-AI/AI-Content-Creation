import os
import time
import shutil
from classes.ContainerManager import ContainerManager
from components.Editor.VideoEditor.VideoEditor import VideoEditor
from components.Editor.ImageEditor.ImageEditor import ImageEditor


def test_video_editor():

    # Create editor (uses temp folder internally)
    veditor = VideoEditor(device_selection = "cpu")
    img_editor = ImageEditor()

    # Input video
    horizontal_video = "volume/resources/videos/background/minecraft/videoplayback.webm"
    vertical_video = "volume/resources/videos/background/subway_surfers/raw1.mp4"

    test = "test02"
    final_output_path = f"volume/output/videoeditor/{test}/"

    # RATIO TESTING -------------------------------------------------------------------------------------------------------------------------------------
    print("\nChanging video ratio...")

    duration = 2 # Secs
    small_h = veditor.cut(horizontal_video, start=0, end=duration) 
    small_v = veditor.cut(vertical_video, start=0, end=duration)


    t0 = time.time()

    # To horizontal 2 vertical
    print("Try: ratio_h2v_crop")
    veditor.change_ratio(
        small_h, ratio="vertical", mode="crop", output_path=os.path.join(final_output_path, "ratio_h2v_crop.mp4")
    )
    print("Try: ratio_h2v_pad_color")
    veditor.change_ratio(
        small_h, ratio="vertical", mode="pad", style={"type": "color", "color": "black"}, output_path=os.path.join(final_output_path, "ratio_h2v_pad_color.mp4")
    )
    print("Try: ratio_h2v_pad_blur")
    veditor.change_ratio(
        small_h, ratio="vertical", mode="pad", style={"type": "blur", "blur_strength":10, "blur_power":5}, output_path=os.path.join(final_output_path, "ratio_h2v_pad_blur.mp4")
    )

    # To vertical 2 wide
    print("Try: ratio_v2h_crop")
    veditor.change_ratio(
        small_v, ratio="widescreen", mode="crop", output_path=os.path.join(final_output_path, "ratio_v2h_crop.mp4")
    )
    print("Try: ratio_v2h_pad_color")
    veditor.change_ratio(
        small_v, ratio="widescreen", mode="pad", style={"type": "color", "color": "#1e8c1b"}, output_path=os.path.join(final_output_path, "ratio_v2h_pad_color.mp4")
    )
    print("Try: ratio_v2h_pad_blur")
    veditor.change_ratio(
        small_v, ratio="widescreen", mode="pad", style={"type": "blur", "blur_strength":20, "blur_power":10}, output_path=os.path.join(final_output_path, "ratio_v2h_pad_blur.mp4")
    )

    # To vertical 2 ultrawide
    print("Try: ratio_v2uw_crop")
    veditor.change_ratio(
        small_v, ratio="ultrawide", mode="crop", output_path=os.path.join(final_output_path, "ratio_v2uw_crop.mp4")
    )
    print("Try: ratio_v2uw_pad_color")
    veditor.change_ratio(
        small_v, ratio="ultrawide", mode="pad", style={"type": "color", "color": "#1e1a99"}, output_path=os.path.join(final_output_path, "ratio_v2uw_pad_color.mp4")
    )
    print("Try: ratio_v2uw_pad_blur")
    veditor.change_ratio(
        small_v, ratio="ultrawide", mode="pad", style={"type": "blur", "blur_strength":40, "blur_power":20}, output_path=os.path.join(final_output_path, "ratio_v2uw_pad_blur.mp4")
    )

    # To wide 2 ultrawide
    print("Try: ratio_h2uw_crop")
    veditor.change_ratio(
        small_h, ratio="ultrawide", mode="crop", output_path=os.path.join(final_output_path, "ratio_h2uw_crop.mp4")
    )
    print("Try: ratio_h2uw_pad_color")
    veditor.change_ratio(
        small_h, ratio="ultrawide", mode="pad", style={"type": "color", "color": "#bf1b68"}, output_path=os.path.join(final_output_path, "ratio_h2uw_pad_color.mp4")
    )
    print("Try: ratio_h2uw_pad_blur")
    veditor.change_ratio(
        small_h, ratio="ultrawide", mode="pad", style={"type": "blur", "blur_strength":60, "blur_power":30}, output_path=os.path.join(final_output_path, "ratio_h2uw_pad_blur.mp4")
    )


    t1 = time.time()

    print(f"Ratio took {t1 - t0:.2f} seconds")



    # FULL EDITING TEST -------------------------------------------------------------------------------------------------------------------------------------

    # 0. Get metadata
    size = veditor.get_size(horizontal_video)
    duration = veditor.get_duration(horizontal_video)
    ratio = veditor.get_ratio(horizontal_video)
    print("\nGetting video meta...")
    print(f"Video size: {size}")
    print(f"Video duration: {duration} ({int(duration/60)}:{int(duration%60)})")
    print(f"Video ratio: {ratio}")


    # 1. Cut the video
    print("\n1. Cutting video...")
    start = 1*60
    new_duration = 2*60
    t0 = time.time()
    video = veditor.cut(horizontal_video, start=start, end=start+new_duration)
    t1 = time.time()
    print("Cut video at:", video)
    print(f"Cutting took {t1 - t0:.2f} seconds")

    duration = veditor.get_duration(video)
    print(f"New Video duration: {duration} ({int(duration/60)}:{(duration%60)})")

    size = veditor.get_size(video)
    print(f"New Video size: {size}")


    # 2. Change ratio
    print("\n2. Changing video ratio...")
    t0 = time.time()
    video = veditor.change_ratio(video, ratio="vertical", mode="crop")
    t1 = time.time()
    print("Video with new ratio at:", video)
    print(f"Ratio took {t1 - t0:.2f} seconds")

    size = veditor.get_size(video)
    ratio = veditor.get_ratio(video)
    print(f"New Video size: {size}")
    print(f"New Video ratio: {ratio}")


    # 3. Add audio
    print("\n3. Adding audio to the video...")
    start = 2 # Seconds
    audio = "volume/resources/audios/test/test01.mp3"
    t0 = time.time()
    video = veditor.replace_audio(video, audio_path=audio, start_time=start)
    t1 = time.time()
    print("Video with audio at:", video)
    print(f"Audio took {t1 - t0:.2f} seconds")


    # 4. Join two videos
    print("\n4. Joining videos...")
    video_aux1 = veditor.cut(horizontal_video, start=30*60, end=30*60 + 5) # Create a 5 sec aux video (1)
    video_aux2 = veditor.cut(horizontal_video, start=55*60, end=55*60 + 5) # Create a 5 sec aux video (2)

    video_aux1 = veditor.change_ratio(video_aux1, ratio="vertical", mode="crop")
    video_aux2 = veditor.change_ratio(video_aux2, ratio="vertical", mode="crop")

    t0 = time.time()
    video = veditor.join([video, video_aux1, video_aux2])
    t1 = time.time()
    print("Joined video at:", video)
    print(f"Join took {t1 - t0:.2f} seconds")

    duration = veditor.get_duration(video)
    print(f"New Video duration: {duration} ({int(duration/60)}:{(duration%60)})")


    # 5. Insert images
    print("\n5. Adding images to the video...")
    image1 = "volume/resources/images/rick/rick_explaining_with_both_hands.png"
    
    image2 = img_editor.load_picture("volume/resources/images/rick/rick_happy_with_cool_sunglasses.png")
    image2 = img_editor.flip(image2, axis="x")
    image2_size = img_editor.get_size(image2)

    image3 = img_editor.load_picture("volume/resources/images/rick/rick_angry_with _portal_gun.png")
    image3 = img_editor.flip(image3, axis="x")
    image3_size = img_editor.get_size(image3)

    image4 = "volume/resources/images/rick/rick_winking_in_approval.png"

    video_size = veditor.get_size(video)

    t0 = time.time()
    video = veditor.insert_images(
        video,
        images=[
            {"image": image1, "start": 5, "end": 15, "x": 0, "y": 100},
            {"image": image2, "start": 20, "end": 30, "x": video_size[0]-image2_size[0], "y": 200},
            {"image": image3, "start": 40, "end": 50, "x": video_size[0]-image3_size[0], "y": video_size[1]-image3_size[1]},
            {"image": image4, "start": 60, "end": 70, "x": 500, "y": 600}
        ]
    )
    t1 = time.time()
    print("Video with image at:", video)
    print(f"Image took {t1 - t0:.2f} seconds")



    # 6. Burn captions with styling
    print("\n6. Burning captions...")

    # Copy last video3 to volume/output/temp.mp4
    # (The video file needs to be inside the volume to be loaded by whisper)
    temp_file = "volume/output/temp.mp4"
    shutil.copy(video, temp_file)
    
    # Start the whisper_container
    whisper_container = ContainerManager(image="whisper:latest", port=8001, use_gpu = True)
    whisper_container.start()
    whisperer = whisper_container.create_client()

    # Set up the model
    whisperer.set_model_size(model_size="medium")
    whisperer.set_params(language="en", task="transcribe")

    # Transcribe a video
    response = whisperer.generate(path="/app/" + temp_file)
    captions = response['answer']

    print("\nCaptions to be inserted:")
    for idx, seg in enumerate(captions):
        text = seg['text'].strip()
        new_text = ""
        line = ""
        for word in text.split():
            if len(line) + len(word) + 1 > 15:
                new_text += line.rstrip() + "\n"
                line = ""
            line += word + " "
        new_text += line.rstrip()
        captions[idx]['text'] = new_text
            
        print(seg)


    # Delete volume/output/temp.mp4
    if os.path.exists(temp_file): os.remove(temp_file)



    t0 = time.time()
    final_video = veditor.insert_captions(
        video,
        captions,
        fontfile="volume/resources/fonts/Roboto_Condensed/static/RobotoCondensed-ExtraBold.ttf",
        fontsize=78,
        fontcolor="yellow",
        borderw=3,
        bordercolor="black",
        shadowx=3,
        shadowy=3,
        x="left",
        y="center",
        padding_x=10,
        padding_y=10,
        text_align="right",
        output_path=os.path.join(final_output_path, "final_editor_test.mp4")
    )
    t1 = time.time()
    

    print("Final video at:", final_video)
    print(f"Captions took {t1 - t0:.2f} seconds")

    # Optional cleanup
    veditor.cleanup()

