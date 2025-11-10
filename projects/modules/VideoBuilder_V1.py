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
        self.veditor = VideoEditor(device_selection = "gpu")
        self.whisperContainer = None
        self.whisperer = None
        self.active = False
        self.background_video = background_video
        random.seed(time.time())

        self.silence_at_start = True
        self.silence_at_end = True
        self.silence_between_character = 0.225
        self.character_padding_y = 100
        self.character_padding_x = 50
        self.logo = 'volume/resources/LoreLabs/logos/LoreLabs_Logo&Letters_png.png'


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
        self.veditor.cleanup()
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
            duration = self.veditor.get_duration(str(audio_path))
            if scene_idx < scene_number-1 or self.silence_at_end:
                duration += self.silence_between_character

            scenes_metadata.append({
                "audio_path": str(audio_path),
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
            {"audio_path": str(metadata['audio_path']), "start": metadata['start'], "volume": 1.25}
            for metadata in scenes_metadata
        ]
        video = self.veditor.mix_audios(video, audio_list)


        # Inserting sound effects
        log.info('Inserting sfx...')
        sfx_bell = 'volume/resources/LoreLabs/sound-effects/notification_bell-1.mp3'
        sfx_whoosh1 = 'volume/resources/LoreLabs/sound-effects/whoosh-1.mp3'
        sfx_whoosh3 = 'volume/resources/LoreLabs/sound-effects/whoosh-3.mp3'
        audio_list = [
            {"audio_path": sfx_whoosh1, "start": metadata['start']}
            if metadata['web_image'] and i != 0 else
            {"audio_path": sfx_whoosh3, "start": metadata['start']}
            for i, metadata in enumerate(scenes_metadata)
        ]
        audio_list.append( {"audio_path": sfx_bell, "start": 0.0, "volume": 0.9} )
        video = self.veditor.mix_audios(video, audio_list)


        log.info('Inserting images...')

        # Insert images
        full_images = []
        flip = True
        video_dim = self.veditor.get_size(video)

        # Add logo
        img = self.img_editor.load_picture(self.logo)
        img = self.img_editor.resize_keep_aspect(img, target_h=video_dim[1]*0.15)
        img_dim = self.img_editor.get_size(img)
        full_images.append({
            "image": img,
            "start": scenes_metadata[0]['start'],
            "end": scenes_metadata[-1]['end'],
            "x": 20,
            "y": video_dim[1] -img_dim[1] - 500,
        })

        # Animation vars
        web_img_transition = 0.15
        char_img_transition = 0.15
        spin_factor = 2.5

        def lerp(s="l", e="c", c="W/2-w/2", p=0, tr=0.5):
            if s == "l": # left to center
                if e == "c": return f"lerp(-w, {c}, t/{tr})"
            if s == "r": # right to center
                if e == "c": return f"lerp(W, {c}, t/{tr})"
            if s == "c": # center to right/left
                if e == "r":  return f"lerp({c}, W, (t-{p})/{tr})"
                if e == "l":   return f"lerp({c}, -w, (t-{p})/{tr})"
 

        for metadata in scenes_metadata:

            flip = not flip

            img = self.img_editor.load_picture(metadata['character_image'])
            img = self.img_editor.resize_keep_aspect(img, target_h=video_dim[1]*0.5)
            img_dim = self.img_editor.get_size(img)

            # Set animation params
            if flip: img = self.img_editor.flip(img, axis="x")

            start, end = metadata['start'], metadata['end']
            duration = end - start

            padding_x = self.character_padding_x if flip else -self.character_padding_x
            x_center = f"(W/2-w/2 + ({padding_x}))"
            y_center = f"(H-h - ({self.character_padding_y}))"

            x_final_spin_pos = f"({x_center}+{img_dim[0]}*0.14*sin(({duration-char_img_transition}-{char_img_transition})*{spin_factor}))"
            y_final_spin_pos = f"({y_center}+{img_dim[0]}*0.14*cos(({duration-char_img_transition}-{char_img_transition})*{spin_factor}))"

            # Add image
            full_images.append({
                "image": img,
                "start": start,
                "end": end,
                "time_base": "image",
                "x": (
                    f"if(lt(t,{char_img_transition}), {lerp(s='r' if flip else 'l', e='c', c=x_center, tr=char_img_transition)}, " # Starting swipe
                    f"if(lt(t,{duration-char_img_transition}), {x_center}+w*0.14*sin((t-{char_img_transition})*{spin_factor}), " # spin
                    f"{lerp(s='c', e='r' if flip else 'l', c=x_final_spin_pos, p=duration-char_img_transition, tr=char_img_transition)}))" # Ending swipe
                ),
                "y": (
                    f"if(lt(t,{char_img_transition}), lerp({y_center}, {y_center}+w*0.14, t/{char_img_transition}), "
                    f"if(lt(t,{duration-char_img_transition}), {y_center}+w*0.14*cos((t-{char_img_transition})*{spin_factor}), "
                    f"lerp({y_final_spin_pos}, {y_center}, (t-{duration-char_img_transition})/{char_img_transition})))"
                ),

            })

            if metadata['web_image']:
                web_img = self.img_editor.load_picture(metadata['web_image'])
                web_img = self.img_editor.resize_keep_aspect(web_img, target_h=video_dim[1]*0.3)
                web_img_dim = self.img_editor.get_size(web_img)

                if web_img_dim[0] > video_dim[0] * 0.7:
                    web_img = self.img_editor.resize_keep_aspect(web_img, target_w=video_dim[0] * 0.7)
                    web_img_dim = self.img_editor.get_size(web_img)

                full_images.append({
                    "image": web_img,
                    "start": start,
                    "end": end,
                    "time_base": "image",
                    "x": ( # slide from left/right to center, stay centered, slide to right/left and disappear
                        f"if(lt(t,{char_img_transition}), {lerp(s='r' if flip else 'l', e='c', c="W/2-w/2", tr=web_img_transition)}, " # Starting swipe
                        f"if(lt(t,{duration-web_img_transition}), W/2-w/2, " # Static
                        f"{lerp(s='c', e='l' if flip else 'r', c="W/2-w/2", p=duration-web_img_transition, tr=web_img_transition)}))" # Ending swipe
                    ),
                    "y": f"H*0.07",
                    "scale": "iw*(1+0.04*sin(t*5)):ih*(1+0.04*sin(t*5))",
                })



        # Save into fixed output to be used for whisper
        file_path = os.path.dirname(save_path) + '/temp.mp4'
        video = self.veditor.insert_images_with_motion(
            video, 
            images=full_images, 
            translation_fps=60,
            output_path=file_path
        )


        log.info('Generate captions...')

        # Seems that whisper its a very picky, crybaby girl.
        video = video.replace("\\", "/")

        # Generate captions
        response = self.whisperer.generate(path=video, client_timeout=300)['answer']
        fixed_subs = self.whisperer.merge_segments(
            word_segments=response,
            words_per_segment=3,
            max_duration=1.5,
            max_pause=0.35,
            max_chars=30
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
            padding_y=+180,
            text_align="center",
            chunk_size=40,
            output_path=save_path
        )

        # Delete images video (temp)
        if os.path.exists(video): os.remove(video)

        return final_video


