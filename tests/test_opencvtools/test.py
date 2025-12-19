from components.MediaAnalyzer.OpenCV.OpenCVTools import OpenCVTools

def test_opencv():

    processor = OpenCVTools()

    timestamps = processor.split_scenes(
        video_path='volume/resources/videos/test/test01.mp4',
        start_time=2.0,
        end_time=30.0
    )

    print(f"Detected {len(timestamps)} scenes.")
    print(timestamps)
