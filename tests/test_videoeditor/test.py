from components.Editor.VideoEditor.VideoEditor import VideoEditor


def test_video_editor():

    # Create editor (uses temp folder internally)
    editor = VideoEditor()

    # Input video
    video = "volume/resources/videos/background/minecraft/videoplayback.webm"
    image = "volume/resources/images/rick/rick_explaining_with_both_hands.png"
    overlay_video = "volume/resources/videos/test/test02.mp4"
    audio = "volume/resources/audios/test/test01.mp3"

    duration = editor.get_duration(video)

    # 0. Cut the video
    print("Cutting video...")
    video0 = editor.cut(video, start=5*60, end=10*60)

    # 1. Insert a logo image between 0s–5s at top-left
    print("Inserting image...")
    video1 = editor.insert_image(video0, image, start=0, end=5, position=(20, 20), center=False)

    print("Overlaying video...")
    # 2. Overlay another video starting at 2s, centered, keep its audio
    video2 = editor.insert_video(video1, overlay_video, start=2, keep_overlay_audio=True)

    print("Muting audio...")
    # 3. Mute audio from 4s–6s
    video3 = editor.mute_audio(video2, start=4, end=6)

    print("Merging audio...")
    # 4. Merge background music, starting at 0s
    video4 = editor.merge_audio(video3, audio, start=0)

    print("Changing speed...")
    # 5. Speed up a segment (6–10s) x2
    video5 = editor.change_speed_segment(video4, start=6, end=10, speed=2.0)

    print("Burning captions...")
    # 6. Burn captions with styling
    captions = [
        {"start": 0.5, "end": 2.1, "text": "Hello world"},
        {"start": 2.2, "end": 4.0, "text": "This is a test"}
    ]
    final_video = editor.set_captions(
        video5,
        captions,
        fontcolor="yellow",
        fontsize=48,
        borderw=3,
        bordercolor="black",
        shadowx=3,
        shadowy=3,
        y="h-(text_h*4)"  # higher above bottom
    )

    print("Final video at:", final_video)

    # Optional cleanup
    editor.cleanup()
