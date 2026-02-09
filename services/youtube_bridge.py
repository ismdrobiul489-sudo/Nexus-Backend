import os
import json
import logging
import httpx
from typing import Optional, Dict, Any
from google_auth_oauthlib.flow import Flow
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request

logger = logging.getLogger(__name__)

class YoutubeBridgeService:
    def __init__(self, storage_dir: str = "server_backup"):
        self.storage_dir = storage_dir
        os.makedirs(self.storage_dir, exist_ok=True)
        os.makedirs(os.path.join(self.storage_dir, "uploads"), exist_ok=True)
        os.makedirs(os.path.join(self.storage_dir, "temp"), exist_ok=True)
        
        self.credentials_path = os.path.join(self.storage_dir, "credentials.json")
        self.tokens_path = os.path.join(self.storage_dir, "tokens.json")
        
        self.scopes = [
            'https://www.googleapis.com/auth/youtube.upload',
            'https://www.googleapis.com/auth/youtube.readonly'
        ]

    def save_config(self, client_id: str, client_secret: str, redirect_uri: Optional[str] = None):
        config = {
            "clientId": client_id,
            "clientSecret": client_secret,
            "redirectUri": redirect_uri
        }
        with open(self.credentials_path, "w") as f:
            json.dump(config, f, indent=2)
        return {"status": "success", "message": "Credentials saved"}

    def load_config(self) -> Optional[Dict[str, Any]]:
        if os.path.exists(self.credentials_path):
            with open(self.credentials_path, "r") as f:
                return json.load(f)
        return None

    def save_tokens(self, tokens: Dict[str, Any]):
        with open(self.tokens_path, "w") as f:
            json.dump(tokens, f, indent=2)

    def load_tokens(self) -> Optional[Dict[str, Any]]:
        if os.path.exists(self.tokens_path):
            with open(self.tokens_path, "r") as f:
                return json.load(f)
        return None

    def get_auth_url(self, redirect_uri: str) -> str:
        config = self.load_config()
        if not config:
            raise ValueError("Credentials not configured.")

        # Construct client_config for the flow
        client_config = {
            "web": {
                "client_id": config["clientId"],
                "client_secret": config["clientSecret"],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [redirect_uri]
            }
        }

        flow = Flow.from_client_config(
            client_config,
            scopes=self.scopes,
            redirect_uri=redirect_uri
        )

        auth_url, _ = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'
        )
        return auth_url

    async def handle_callback(self, code: str, redirect_uri: str):
        config = self.load_config()
        if not config:
            raise ValueError("Credentials missing during callback.")

        client_config = {
            "web": {
                "client_id": config["clientId"],
                "client_secret": config["clientSecret"],
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        }

        flow = Flow.from_client_config(
            client_config,
            scopes=self.scopes,
            redirect_uri=redirect_uri
        )
        flow.fetch_token(code=code)
        
        creds = flow.credentials
        tokens = {
            'token': creds.token,
            'refresh_token': creds.refresh_token,
            'token_uri': creds.token_uri,
            'client_id': creds.client_id,
            'client_secret': creds.client_secret,
            'scopes': creds.scopes
        }
        self.save_tokens(tokens)
        return tokens

    def get_status(self):
        config = self.load_config()
        tokens = self.load_tokens()
        return {
            "configured": config is not None,
            "connected": tokens is not None,
            "tokens": tokens
        }

    async def upload_video(self, video_path: str, title: str, description: str, 
                           tags: list = None, privacy: str = "private", 
                           hf_token: str = None, tokens: Dict[str, Any] = None):
        
        config = self.load_config()
        saved_tokens = self.load_tokens()
        active_tokens = tokens or saved_tokens

        if not config or not active_tokens:
            raise ValueError("Not authenticated. Please login first.")

        creds = Credentials(
            token=active_tokens.get('token'),
            refresh_token=active_tokens.get('refresh_token'),
            token_uri=active_tokens.get('token_uri'),
            client_id=active_tokens.get('client_id'),
            client_secret=active_tokens.get('client_secret'),
            scopes=active_tokens.get('scopes')
        )

        # Refresh if needed
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            # Save refreshed tokens if it was the local ones
            if not tokens:
                self.save_tokens({
                    'token': creds.token,
                    'refresh_token': creds.refresh_token,
                    'token_uri': creds.token_uri,
                    'client_id': creds.client_id,
                    'client_secret': creds.client_secret,
                    'scopes': creds.scopes
                })

        youtube = build('youtube', 'v3', credentials=creds)

        local_file_path = video_path

        # Handle URL download
        if video_path.startswith(('http://', 'https://')):
            logger.info("Detected URL, downloading video...")
            temp_dir = os.path.join(self.storage_dir, "temp")
            import time
            temp_file = os.path.join(temp_dir, f"download_{int(time.time())}.mp4")

            headers = {'User-Agent': 'NCAKit-Uploader/1.0'}
            if hf_token and "huggingface.co" in video_path:
                headers['Authorization'] = f"Bearer {hf_token}"
                logger.info("Using HF Token for authenticated download")

            async with httpx.AsyncClient(follow_redirects=True) as client:
                resp = await client.get(video_path, headers=headers)
                if resp.status_code != 200:
                    raise Exception(f"Failed to download video: {resp.status_code}")
                
                with open(temp_file, "wb") as f:
                    f.write(resp.content)
            
            local_file_path = temp_file
            logger.info(f"Saved to: {local_file_path}")

        if not os.path.exists(local_file_path):
            raise FileNotFoundError(f"File not found: {local_file_path}")

        body = {
            'snippet': {
                'title': title or 'New Video',
                'description': description or '',
                'tags': tags or []
            },
            'status': {
                'privacyStatus': privacy or 'private'
            }
        }

        media = MediaFileUpload(local_file_path, chunksize=-1, resumable=True)
        request = youtube.videos().insert(part='snippet,status', body=body, media_body=media)
        
        response = None
        while response is None:
            status, response = request.next_chunk()
            if status:
                logger.info(f"Uploaded {int(status.progress() * 100)}%")

        logger.info(f"Upload successful: {response.get('id')}")
        return {
            "success": True,
            "videoId": response.get('id'),
            "videoUrl": f"https://youtu.be/{response.get('id')}"
        }
