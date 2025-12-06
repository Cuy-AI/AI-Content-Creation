from datetime import datetime, timedelta
from components.Uploaders.YouTube.YouTubeUploader import YouTubeUploader

def test_UploaderYT():
    
    # Creating a new token file with my channel name
    print("\n--- Creating/Loading token ---")
    yt_uploader_1 = YouTubeUploader(token_file="components/Uploaders/YouTube/tokens/Lore Labs - Tech & CS.json") 

    
    # Set video meta
    print("\n--- Crating video details ---")
    VIDEO_PATH = 'volume/resources/videos/test/test02.mp4'
    video_details = {
        'title': 'My Amazing Python Upload Test',
        'description': 'This video was uploaded using the YouTube Data API with a custom Python script!',
        'tags': ['python', 'youtube api', 'coding', 'automation'],
        'category_id': '28', # Science & Technology
        'language': 'en', # English
        'privacy_status': 'private', 
        # To schedule a video:
        'schedule_at': YouTubeUploader.convert_to_schedule_time(datetime.now() + timedelta(days=1))
    }


    # Upload video
    print("\n--- Uploading video ---")
    video_response_1 = yt_uploader_1.upload_video(VIDEO_PATH, video_details)
    video_id_1 = video_response_1['id']
    print(f"Uploaded Video ID: {video_id_1}")


    # Set thumbnail
    # Do not use this unless you read the NOTE on the definition of the method.
    # print("\n--- Setting thumbnail ---")
    # THUMBNAIL_PATH = 'volume/resources/images/comfyui/pic.png'
    # yt_uploader_1.set_thumbnail(video_id_1, THUMBNAIL_PATH)


    # SECOND CHANNEL - SAME GOOGLE ACCOUNT --------------------------------------------------------------------

    # Creating a second token file with my channel name
    print("\n--- Creating/Loading token ---")
    yt_uploader_2 = YouTubeUploader(token_file="components/Uploaders/YouTube/tokens/TheUnsocialDude.json") 

    
    # Set video meta
    print("\n--- Crating video details ---")
    VIDEO_PATH = 'volume/resources/videos/test/test02.mp4'
    video_details = {
        'title': 'My Amazing Python Upload Test 2',
        'description': 'This video was uploaded using the YouTube Data API with a custom Python script!',
        'tags': ['python', 'youtube api', 'coding', 'automation', 'channel'],
        'category_id': '28', # Science & Technology
        'language': 'en', # English
        'privacy_status': 'private', 
        # To schedule a video:
        'schedule_at': YouTubeUploader.convert_to_schedule_time(datetime.now() + timedelta(hours=10))
    }


    # Upload video
    print("\n--- Uploading video ---")
    video_response_1 = yt_uploader_2.upload_video(VIDEO_PATH, video_details)
    video_id_1 = video_response_1['id']
    print(f"Uploaded Video ID: {video_id_1}")




