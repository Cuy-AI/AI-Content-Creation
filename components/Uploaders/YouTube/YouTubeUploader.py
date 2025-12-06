import os
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone

import google.oauth2.credentials
import google_auth_oauthlib.flow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


class YouTubeUploader:
    """
    A class to handle uploading videos to YouTube using the GCP YouTube Data API v3.
    It manages authentication, video uploads, metadata setting, and thumbnail uploads.
    """

    def __init__(self, token_file:str, scopes:list = None):
        """
        Initializes the YouTubeUploader with authentication.
        :param token_file: Path to the token file for storing OAuth2 credentials.
        :param scopes: List of OAuth2 scopes. Defaults to ['https://www.googleapis.com/auth/youtube.upload'].
        NOTE: 
            If you don't have a token yet, the authentication flow will create one for you.
            Set your token_file to something like: components/Uploaders/YouTube/tokens/my_channel_name.json
            The created token file will store your access to a specific YT channel. 
            (Remember that a single google account can have multiple YT channels).
        """

        # Load client_secret.json
        load_dotenv()
        self.CLIENT_SECRETS_FILE = os.getenv('YOUTUBE_CLIENT_SECRET_PATH', None)
        if not self.CLIENT_SECRETS_FILE: raise ValueError("YOUTUBE_CLIENT_SECRET_PATH environment variable is not set.")

        # Set up scopes
        # Default: youtube.upload is the scope for uploading videos. It also includes permission to manage videos.
        if not scopes: self.SCOPES = ['https://www.googleapis.com/auth/youtube.upload']
        else: self.SCOPES = scopes

        # Set up the channel tokens
        self.set_authentication_service(token_file)        



    def set_authentication_service(self, token_file:str):
        """Initializes the YouTube API service object."""

        # You may want to set up all your tokens inside: components/Uploaders/YouTube/tokens/my_token.json
        self.token_file = token_file

        # Create the flow using the client secrets file from the Google API Console.
        flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(self.CLIENT_SECRETS_FILE, self.SCOPES)
        
        # Try to load saved credentials
        credentials = None
        if os.path.exists(self.token_file):
            credentials = google.oauth2.credentials.Credentials.from_authorized_user_file(self.token_file, self.SCOPES)
        
        # If credentials are not valid or don't exist, start the flow
        if not credentials or not credentials.valid:
            if credentials and credentials.expired and credentials.refresh_token:
                credentials.refresh(google.auth.transport.requests.Request())
            else:
                flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(self.CLIENT_SECRETS_FILE, self.SCOPES)
                # The authorization page will open in your browser
                credentials = flow.run_local_server(port=0)

            # Save the credentials for the next run
            with open(self.token_file, 'w') as token:
                token.write(credentials.to_json())

        # Build the service object
        self.youtube = build('youtube', 'v3', credentials=credentials)



    def upload_video(self, video_file, metadata):
        """
        Uploads a video and sets its metadata.
        
        :param video_file: Path to the video file (e.g., 'my_video.mp4')
        :param metadata: A dictionary containing video details. Must contain a title
        """
        
        # 1. Define the snippet and status resources
        snippet = {
            'title': metadata['title'],
            'description': metadata.get('description', ''),
            'tags': metadata.get('tags', []), # Optional
            'categoryId': metadata.get('category_id', '22'), # Default to 'People & Blogs'
            'defaultLanguage': metadata.get('language', 'en'),
        }

        # Status controls privacy, scheduling, and license
        status = {
            'privacyStatus': metadata.get('privacy_status', 'private'), # 'public', 'private', or 'unlisted'
            'embedddable': metadata.get('embeddable', True),
            'license': metadata.get('license', 'youtube'), # 'youtube' or 'creativeCommon'
            'selfDeclaredMadeForKids': metadata.get('made_for_kids', False)
        }
        
        # Set schedule, if provided
        schedule_time = metadata.get('schedule_at')
        if schedule_time:
            # YouTube API requires ISO 8601 format (e.g., '2025-11-20T10:00:00.000Z')
            # The required format is YYYY-MM-DDT_HH:MM:SS.000Z
            status['publishAt'] = schedule_time 
            status['privacyStatus'] = 'private' # Must be 'private' if 'publishAt' is set
            
        
        # 2. Define the request body
        body = {
            'snippet': snippet,
            'status': status,
            # 'localizations' can be used for other languages, but it's complex for a basic example
        }
        
        # 3. Create the MediaFileUpload object
        media_file = MediaFileUpload(video_file, chunksize=-1, resumable=True)
        
        # 4. Initiate the upload
        insert_request = self.youtube.videos().insert(
            part='snippet,status',
            body=body,
            media_body=media_file
        )
        
        response = insert_request.execute()
        return response
    

        
    def set_thumbnail(self, video_id, image_file):
        """
        Sets a custom thumbnail for the uploaded video.
        NOTE:
            This method will not work unless you verify your phone number for your YT channel
            Up to two yt channels can be verified per phone number, per year.
            Verifying your phone number will allow you to monetize your channel, so you can only bet on 2 accounts per year.
            (Unless you have multiple phone numbers)
        """

        media_file = MediaFileUpload(image_file)
        
        request = self.youtube.thumbnails().set(
            videoId=video_id,
            media_body=media_file
        )
        response = request.execute()
        return response
    


    # UTILS -------------------------------------------------------------------
    @staticmethod
    def convert_to_schedule_time(dt: datetime, future_minutes: int = 30) -> str:
        """
        Converts a datetime object into the required ISO 8601 format for YouTube's 
        'publishAt' and ensures the time is at least 'future_minutes' in the future.

        YouTube requires the format: YYYY-MM-DDT_HH:MM:SS.000Z (Zulu Time/UTC)
        
        :param dt: The desired datetime object (can be naive or timezone-aware).
        :param future_minutes: The minimum number of minutes the scheduled time must be 
                               in the future from the current time. Youtube doesn't 
                               accept schedule times closer to current time.
        :return: A UTC-based ISO 8601 string suitable for the YouTube API.
        """
        
        # 1. Make the time UTC-aware if it's not
        if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
            # Assume local time and convert to UTC
            dt = dt.astimezone(timezone.utc)
        else:
            # Ensure it is in UTC
            dt = dt.astimezone(timezone.utc)
            
        # 2. Ensure the scheduled time is in the future
        now_utc = datetime.now(timezone.utc)
        minimum_future_time = now_utc + timedelta(minutes=future_minutes)

        if dt < minimum_future_time:
            # Set the time to the minimum required future time (plus a second buffer)
            dt = minimum_future_time + timedelta(seconds=5)

        # 3. Format the string to the strict YouTube ISO 8601 format (milliseconds precision is often safest)
        # Using Z for UTC/Zulu time. We round to the nearest second and then append .000Z
        
        # Round to the nearest second
        dt = dt.replace(microsecond=0) 
        
        # Format: YYYY-MM-DDTHH:MM:SS.000Z
        # We append .000Z because dt.isoformat() includes a '+' sign for the timezone, which YouTube dislikes for UTC
        # If dt.tzinfo is set to timezone.utc, dt.isoformat() will end with '+00:00'. We replace it with 'Z'.
        
        formatted_time = dt.isoformat().replace('+00:00', '.000Z')
        
        return formatted_time