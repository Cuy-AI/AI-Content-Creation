from scenedetect import detect, ContentDetector

class OpenCVTools:
    def __init__(self): pass

    def split_scenes(self, video_path, start_time=0, end_time=None, threshold=27):
        """
        Processes a video within a specific time range.
        
        :param video_path: Path to the video file.
        :param start_time: Start position (seconds). Defaults to 0.
        :param end_time: End position (seconds). Defaults to None (end of video).
        :return: A list of dictionaries containing detailed scene metadata.
        """

        detector = ContentDetector(threshold=threshold)

        # Run detection with the start_pos and end_pos arguments
        # These can accept seconds as floats directly
        scene_list = detect(
            video_path, 
            detector, 
            start_time=start_time, 
            end_time=end_time
        )

        detailed_scenes = []
        for i, scene in enumerate(scene_list):
            start, end = scene
            
            # scene[0] and scene[1] are FrameTimecode objects
            scene_data = {
                "scene_number": i + 1,
                "start_seconds": start.get_seconds(),
                "end_seconds": end.get_seconds(),
                "duration_seconds": end.get_seconds() - start.get_seconds(),
                "start_frame": start.get_frames(),
                "end_frame": end.get_frames(),
            }
            detailed_scenes.append(scene_data)

        return detailed_scenes