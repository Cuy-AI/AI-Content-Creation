from datetime import datetime, timedelta, timezone
from components.Uploaders.Meta.MetaUploader import MetaUploader

def test_UploaderMeta():
    
    uploader = MetaUploader('components/Uploaders/Meta/tokens/Lore Labs - Tech & CS.json')
    video_file = 'volume/output/LoreLabs/Workflow 2/00008/6 - build_video/History of Computing.mp4'
    
    # Schedule for 30 minutes from now (must be timezone-aware)
    schedule_dt = datetime.now(timezone.utc) + timedelta(minutes=60)
    
    # IG Reel Upload Example
    ig_id = uploader.publish_reel_ig(
        file_path=video_file,
        caption="My awesome new IG Reel! #reels ☀️😎",
    )
    print(f"\nFinal IG Reel ID: {ig_id}")
    
    # FB Reel Upload Example
    fb_id = uploader.publish_reel_fb(
        file_path=video_file,
        description="What a beautiful day! ☀️😎 #sunnyand72",
        scheduled_time=schedule_dt
    )
    print(f"\nFinal FB Reel ID: {fb_id}")