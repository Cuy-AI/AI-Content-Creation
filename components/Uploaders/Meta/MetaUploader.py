import requests
import json
from datetime import datetime, timezone, timedelta
import os
import time
from typing import Dict, Any, Optional

# --- Constants for FB/IG differentiation ---
class EntityType:
    INSTAGRAM = 'IG'
    FACEBOOK = 'FB'

# --- Configuration Constants ---
API_VERSION = 'v24.0'
GRAPH_URL = f"https://graph.facebook.com/{API_VERSION}"
UPLOAD_HOST = "https://rupload.facebook.com"


# --- Helper Function for Scheduling ---
def datetime_to_unix_timestamp(dt: datetime) -> int:
    """Converts a datetime object to a Unix timestamp (seconds since epoch)."""
    if dt.tzinfo is None or dt.tzinfo.utcoffset(dt) is None:
        # If naive, assume UTC for API consistency
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())

class MetaUploader:
    """
    Handles FB + IG Reel publishing, including local file Resumable Upload,
    following the official Meta API documentation.
    """
    
    # --- Initialization ---
    
    def __init__(self, secrets_file: str):
        """
        :param secrets_file: 
            A path to a json file that contains:
            - "access_token" -> MANDATORY: Your FB page access token 
            - "page_id" -> OPT: Your FB page id
            - "ig_user_id" -> OPT: Your IG user id
        """
        self._loadCredentials(secrets_file)

    def _loadCredentials(self, secrets_file:str):
        """Loads credentials from the specified JSON file."""
        self.secrets_file = secrets_file

        try:
            with open(secrets_file, 'r') as f: secrets = json.load(f)
        except FileNotFoundError: raise FileNotFoundError(f"Secrets file not found: {secrets_file}")
        except json.JSONDecodeError: raise ValueError(f"Invalid JSON in secrets file: {secrets_file}")

        if 'access_token' not in secrets: raise KeyError("access_token not found in secrets file")
        if 'ig_user_id' not in secrets and 'page_id' not in secrets: 
             raise KeyError("Neither ig_user_id nor page_id found in secrets file. Need at least one.")

        self.ACCESS_TOKEN = secrets['access_token']
        self.IG_USER_ID = secrets.get('ig_user_id', None) 
        self.PAGE_ID = secrets.get('page_id', None) 

    # --- Core Utility Methods ---

    def _makeRequest(self, method: str, url: str, params: Optional[Dict[str, Any]] = None, data: Optional[Dict[str, Any]] = None, files: Optional[Dict[str, Any]] = None, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Generic request handler with error checking."""
        
        # Add access_token to params if not in data/files (common for GET/some POSTs)
        if params is None:
            params = {}
        if method == 'GET' and 'access_token' not in params:
            params['access_token'] = self.ACCESS_TOKEN
        
        try:
            response = requests.request(method, url, params=params, data=data, files=files, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            # print(f"HTTP Error: {e.response.text}")
            raise
        except requests.exceptions.RequestException as e:
            # print(f"Request Error: {e}")
            raise


    def _uploadFile(self, upload_url: str, file_path: str) -> bool:
        """Handles the actual binary file transfer using resumable upload with retries."""
        
        file_size = os.path.getsize(file_path)
        # print(f"Uploading file '{os.path.basename(file_path)}' ({file_size} bytes)...")

        max_attempts = 3
        
        for attempt in range(1, max_attempts + 1):
            # print(f"\n🔄 Attempt {attempt}/{max_attempts}")

            headers = {
                "Authorization": f"OAuth {self.ACCESS_TOKEN}",
                "offset": "0",
                "file_size": str(file_size)
            }

            try:
                with open(file_path, 'rb') as f:
                    response = requests.post(upload_url, data=f, headers=headers, timeout=500)

                try:
                    result = response.json()
                except ValueError:
                    # print(f"❌ Invalid JSON response: {response.text}")
                    result = {}

                # Check success conditions
                if result.get("success") is True or result.get("message") == "Upload successful.":
                    # print("✅ Upload successful.")
                    return True

                # If upload failed but JSON exists
                # print(f"❌ Upload failed:\n{result}")

            except requests.exceptions.HTTPError as e:
                print(f"❌ HTTP Error:\n{e.response.text}")

            except requests.exceptions.RequestException as e:
                print(f"❌ Request Error:\n{e}")

            # If here, upload failed → retry unless last attempt
            if attempt < max_attempts:
                # print("⏳ Retrying in 1.5 seconds...")
                time.sleep(1.5)

        # print("❌ Upload failed after 3 attempts.")
        return False




    def _waitForProcessing(self, media_id: str, platform: str, timeout: int = 300, interval: int = 5) -> bool:
        """Waits for the video to finish processing."""
        
        if platform == EntityType.INSTAGRAM:
            status_field = 'status_code'
            success_status = 'FINISHED'
            url = f"{GRAPH_URL}/{media_id}"
            
        elif platform == EntityType.FACEBOOK:
            status_field = 'status'
            success_status = 'complete'
            url = f"{GRAPH_URL}/{media_id}"

        # print(f"Waiting for {platform} media {media_id} to finish processing...")
        start_time = time.time()

        while time.time() - start_time < timeout:
            status_response = self._makeRequest('GET', url, params={'fields': status_field})
            
            if platform == EntityType.INSTAGRAM:
                current_status = status_response.get(status_field)
                if current_status == success_status:
                    # print("Processing finished.")
                    return True
                elif current_status in ('EXPIRED', 'ERROR'):
                    # print(f"Processing failed: {current_status}")
                    return False
                # print(f"Status: {current_status}...")

            elif platform == EntityType.FACEBOOK:
                video_status = status_response.get(status_field, {}).get('video_status')
                if video_status in ('complete', 'ready'): 
                    # print("Processing finished.")
                    return True
                elif video_status in ('error', 'fail'):
                    # print(f"Processing failed: {video_status}")
                    return False
                # print(f"Status: {video_status}...")

            time.sleep(interval)

        # print("Timeout reached while waiting for processing.")
        return False

    # --- Platform-Specific Publishing Methods ---

    def publish_reel_ig(self, file_path: str, caption: str) -> Optional[str]:
        """
        Publishes a Reel to Instagram.
        :param file_path: Local path to the video file.
        :param caption: The text caption for the Reel.
        :return: The published Instagram Media ID on success, or None on failure.
        """
        if not self.IG_USER_ID: raise ValueError("IG_USER_ID not configured in secrets.")
        
        # 1. Start Resumable Upload & Create Container
        params = {
            'media_type': 'REELS',
            'upload_type': 'resumable',
            'caption': caption,
            'access_token': self.ACCESS_TOKEN
        }

        # print("1. Creating Instagram media container...")
        response = self._makeRequest('POST', f"{GRAPH_URL}/{self.IG_USER_ID}/media", params=params)
        ig_container_id = response.get('id')
        upload_url = response.get('uri') # IG uploads to the /ig-api-upload/ endpoint, which is returned in 'uri'
        
        if not ig_container_id or not upload_url:
            # print("Failed to create container.")
            return None

        # 2. Upload the file
        if not self._uploadFile(upload_url, file_path):
            return None

        # 3. Wait for processing (status_code == FINISHED)
        if not self._waitForProcessing(ig_container_id, EntityType.INSTAGRAM):
            return None

        # 4. Publish the container
        # print("4. Publishing Instagram Reel...")
        publish_data = {
            'creation_id': ig_container_id,
            'access_token': self.ACCESS_TOKEN
        }

        publish_response = self._makeRequest('POST', f"{GRAPH_URL}/{self.IG_USER_ID}/media_publish", data=publish_data)
        
        return publish_response.get('id')


    
    def publish_reel_fb(self, file_path: str, description: str, scheduled_time: Optional[datetime] = None) -> Optional[str]:
        """
        Publishes a Reel to Facebook.
        :param file_path: Local path to the video file.
        :param description: The text description/caption for the Reel.
        :param scheduled_time: Optional datetime object for scheduling.
        :return: The published Facebook Post ID on success, or None on failure.
        """
        if not self.PAGE_ID: raise ValueError("PAGE_ID not configured in secrets.")

        # 1. Start Resumable Upload Session
        start_data = {
            'upload_phase': 'start',
            'access_token': self.ACCESS_TOKEN
        }
        
        # print("1. Starting Facebook Reel upload session...")
        response = self._makeRequest('POST', f"{GRAPH_URL}/{self.PAGE_ID}/video_reels", data=start_data)
        video_id = response.get('video_id')
        upload_url = response.get('upload_url')

        if not video_id or not upload_url:
            # print("Failed to start upload session.")
            return None

        # 2. Upload the file
        if not self._uploadFile(upload_url, file_path):
            return None

        # 3. Finish Upload and Publish (Triggers Processing)
        finish_data = {
            'access_token': self.ACCESS_TOKEN,
            'video_id': video_id,
            'upload_phase': 'finish',
            'description': description
        }

        # Set scheduling or immediate publish state
        if scheduled_time:
            timestamp = datetime_to_unix_timestamp(scheduled_time)
            finish_data['scheduled_publish_time'] = timestamp
            finish_data['video_state'] = 'SCHEDULED'
            # print(f"3. Finishing upload and scheduling Facebook Reel for {scheduled_time}...")
        else:
            finish_data['video_state'] = 'PUBLISHED'
            # print("3. Finishing upload and publishing Facebook Reel...")

        publish_response = self._makeRequest('POST', f"{GRAPH_URL}/{self.PAGE_ID}/video_reels", data=finish_data)
        
        # 4. Wait for processing (for immediate publish or to confirm schedule)
        # print("4. Waiting for processing to confirm final status...")
        if not self._waitForProcessing(video_id, EntityType.FACEBOOK):
             # print("Video processing failed or timed out. Check video status manually.")
             # We still return the post ID if available, as the processing failure is asynchronous.
             pass 

        return publish_response.get('post_id') or publish_response.get('id')

