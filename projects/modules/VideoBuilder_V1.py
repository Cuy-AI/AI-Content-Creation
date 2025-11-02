import os
import time
import random
from prefect import get_run_logger
from classes.ContainerManager import ContainerManager
from components.Editor.VideoEditor.VideoEditor import VideoEditor
from components.Editor.ImageEditor.ImageEditor import ImageEditor


class VideoBuilder_V1:

    def __init__(self, background_video:str = None):
        self.img_editor = ImageEditor()
        self.veditor = VideoEditor(device_selection = "cpu")
        self.whisperContainer = None
        self.whisperer = None
        self.active = False
        self.background_video = background_video
        random.seed(time.time())

        self.silence_at_start = True
        self.silence_at_end = True
        self.silence_between_character = 0.225
        self.character_padding_y = 50
        self.character_padding_x = 50


    def start(self):
        if self.active: return
        self.whisperContainer = ContainerManager(image="whisper:latest", port=8001, use_gpu = True)
        self.whisperContainer.start()
        self.whisperer = self.whisperContainer.create_client()
        self.whisperer.set_model_size(model_size="medium", client_timeout = 180)
        self.whisperer.set_params(language="en", task="transcribe", word_timestamps=True)
        self.active = True

    def stop(self):
        if not self.active: return
        self.whisperContainer.stop()
        self.active = False
    
    def build_full_video(self, script:dict, audios:list, images:dict, save_path:str):


        log = get_run_logger()
        log.info('Collecting metadata...')

        # Create metadata
        scenes_metadata = []
        scene_number = len(script['scenes'])
        accumulated_time = self.silence_between_character if self.silence_at_start else 0
        for scene, audio_path in zip(script['scenes'], audios):
            
            scene_idx = scene['id']
            duration = self.veditor.get_duration(audio_path)
            if scene_idx < scene_number-1 or self.silence_at_end:
                duration += self.silence_between_character

            scenes_metadata.append({
                "audio_path": audio_path,
                "character_image": scene['character_image'],
                "web_image": images.get(str(scene_idx), None),
                "start": accumulated_time,
                "end": accumulated_time + duration,
                "duration": duration
            })

            accumulated_time += duration


        log.info('Cutting video...')

        # Cut background video 
        background_duration = self.veditor.get_duration(self.background_video)
        
        '''
        Fast cut:  
        It takes less than a second
        Error of +- 3 seconds
        But some forums suggest the error can even be +- 10 seconds
        '''
        # fixed_background_duration = background_duration - accumulated_time - 1
        # select_start = random.random() * fixed_background_duration
        # select_end = select_start + accumulated_time
        # video = self.veditor.cut(background_video, start=select_start, end=select_end, reencode=False) 

        '''
        Accurate cut:  
        It takes like 30 seconds
        No error
        '''
        fixed_background_duration = background_duration - accumulated_time - 1
        select_start = round(random.random() * fixed_background_duration, 2)
        select_end = round(select_start + accumulated_time, 2)
        video = self.veditor.cut(self.background_video, start=select_start, end=select_end, reencode=True) 


        log.info('Changing ratio...')

        # Change ratio
        video = self.veditor.change_ratio(video, ratio="vertical", mode="crop")

        log.info('Inserting voices...')

        # Insert audios
        audio_list = [
            {"audio_path": metadata['audio_path'], "start": metadata['start']}
            for metadata in scenes_metadata
        ]
        video = self.veditor.mix_audios(video, audio_list)


        log.info('Inserting images...')

        # Insert images
        full_images = []
        flip = False
        video_dim = self.veditor.get_size(video)
        for metadata in scenes_metadata:
            
            img = self.img_editor.load_picture(metadata['character_image'])
            img = self.img_editor.resize_keep_aspect(img, target_h=video_dim[1]*0.3)
            img_dim = self.img_editor.get_size(img)

            if flip: img = self.img_editor.flip(img, axis="x")

            padding_x = self.character_padding_x if flip else -self.character_padding_x
            full_images.append({
                "image": img,
                "start": metadata['start'],
                "end": metadata['end'],
                "x": (video_dim[0]/2) - (img_dim[0]/2) + padding_x,
                "y": video_dim[1]-img_dim[1] - self.character_padding_y
            })

            flip = not flip

            if metadata['web_image']:
                web_img = self.img_editor.load_picture(metadata['web_image'])
                web_img = self.img_editor.resize_keep_aspect(web_img, target_h=video_dim[1]*0.3)
                web_img_dim = self.img_editor.get_size(web_img)

                if web_img_dim[0] > video_dim[0] * 0.7:
                    web_img = self.img_editor.resize_keep_aspect(web_img, target_w=video_dim[0] * 0.7)
                    web_img_dim = self.img_editor.get_size(web_img)

                full_images.append({
                    "image": web_img,
                    "start": metadata['start'],
                    "end": metadata['end'],
                    "x": (video_dim[0]/2) - (web_img_dim[0]/2),
                    "y": video_dim[1]*0.08
                })

        # Save into fixed output to be used for whisper
        file_path = os.path.dirname(save_path) + '/temp.mp4'
        video = self.veditor.insert_images(video, images=full_images, output_path=file_path)
        

        log.info('Generate captions...')

        # Seems that whisper its a very picky, crybaby girl.
        video = video.replace("\\", "/")

        # Generate captions
        response = self.whisperer.generate(path=video, client_timeout=300)['answer']
        fixed_subs = self.whisperer.merge_segments(
            word_segments=response, 
            words_per_segment=3, 
            max_duration=1.5,
            max_pause=0.35
        )['answer']


        log.info('Inserting captions...')

        # Insert captions
        final_video = self.veditor.insert_captions(
            video,
            fixed_subs,
            fontfile="volume/resources/fonts/Roboto_Condensed/static/RobotoCondensed-ExtraBold.ttf",
            fontsize=82,
            fontcolor="yellow",
            borderw=3,
            bordercolor="black",
            shadowx=3,
            shadowy=3,
            x="center",
            y="center",
            text_align="center",
            output_path=save_path
        )

        # Delete images video (temp)
        if os.path.exists(video): os.remove(video)

        self.veditor.cleanup()

        return final_video


