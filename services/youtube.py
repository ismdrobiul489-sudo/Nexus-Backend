import httpx
import os
import json
from typing import Optional, Dict, Any, List
from utils.temp_file_manager import TempFileManager

class YouTubeService:
    OAUTH_TOKEN_URL = 'https://oauth2.googleapis.com/token'
    YOUTUBE_UPLOAD_URL = 'https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status'

    @classmethod
    async def refresh_access_token(cls, client_id: str, client_secret: str, refresh_token: str) -> str:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(cls.OAUTH_TOKEN_URL, data={
                'client_id': client_id,
                'client_secret': client_secret,
                'refresh_token': refresh_token,
                'grant_type': 'refresh_token',
            })
            
            data = response.json()
            if response.status_code != 200 or "access_token" not in data:
                raise Exception(f"YouTube Token Refresh Failed: {data.get('error_description', data.get('error', 'Unknown error'))}")
                
            return data["access_token"]

    @classmethod
    async def verify_credentials(cls, client_id: str, client_secret: str, refresh_token: str = None) -> bool:
        """Validates credentials by attempting to refresh the token (Strict Parity)."""
        if not client_id or not client_secret:
            raise Exception("Client ID and Secret are required")
        
        if refresh_token:
            try:
                # Actual verification via API
                await cls.refresh_access_token(client_id, client_secret, refresh_token)
                return True
            except Exception as e:
                print(f"Credential Verification Failed: {e}")
                return False
        
        # Fallback format check if no refresh token (Legacy)
        if not client_id.endswith(".apps.googleusercontent.com"):
             raise Exception("Invalid Client ID format")
        return True

    @classmethod
    async def get_channel_profile(cls, client_id: str, client_secret: str, refresh_token: str) -> Dict[str, str]:
        """Fetches Channel ID, Name, and Thumbnail (1:1 Parity with getChannelProfile)."""
        access_token = await cls.refresh_access_token(client_id, client_secret, refresh_token)
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                "https://www.googleapis.com/youtube/v3/channels",
                params={"part": "snippet", "mine": "true"},
                headers={"Authorization": f"Bearer {access_token}"}
            )
            
            data = response.json()
            if response.status_code != 200 or "items" not in data:
                raise Exception(f"Failed to fetch profile: {data.get('error', 'Unknown error')}")
                
            if not data["items"]:
                raise Exception("No Channel found for these credentials.")
                
            snippet = data["items"][0]["snippet"]
            return {
                "id": data["items"][0]["id"],
                "name": snippet["title"],
                "thumbnail": snippet.get("thumbnails", {}).get("default", {}).get("url", "")
            }

    @classmethod
    async def upload_video(
        cls,
        client_id: str,
        client_secret: str,
        refresh_token: str,
        file_path_or_url: str,
        metadata: Dict[str, Any]
    ) -> str:
        """Uploads a video to YouTube using Resumable Upload (Mirroring mobile's protocol)"""
        temp_file = None
        
        try:
            # 1. Handle URL Download (1:1 with Frontend)
            if file_path_or_url.startswith(("http://", "https://")):
                print(f"[YouTube] Downloading video from URL: {file_path_or_url}")
                temp_file = await TempFileManager.download_file(file_path_or_url, f"yt_upload_{os.urandom(4).hex()}.mp4")
                file_path = temp_file
            else:
                file_path = file_path_or_url

            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found: {file_path}")
                
            access_token = await cls.refresh_access_token(client_id, client_secret, refresh_token)
            file_size = os.path.getsize(file_path)
            
            async with httpx.AsyncClient(timeout=300.0) as client:
                # 2. Initiate Resumable Session
                headers = {
                    'Authorization': f'Bearer {access_token}',
                    'Content-Type': 'application/json',
                    'X-Upload-Content-Length': str(file_size),
                    'X-Upload-Content-Type': 'video/mp4'
                }
                body = {
                    "snippet": {
                        "title": metadata.get("title", "Untitled Video")[:100],
                        "description": metadata.get("description", "")[:5000],
                        "tags": metadata.get("tags", []),
                        "categoryId": metadata.get("categoryId", "22")
                    },
                    "status": {
                        "privacyStatus": metadata.get("privacy", "private"),
                        "selfDeclaredMadeForKids": False
                    }
                }
                
                init_res = await client.post(cls.YOUTUBE_UPLOAD_URL, headers=headers, json=body)
                if init_res.status_code != 200:
                    raise Exception(f"YouTube Init Failed: {init_res.text}")
                    
                upload_url = init_res.headers.get('Location')
                if not upload_url:
                    raise Exception("YouTube Init Failed: No Location Header returned.")
                
                # 3. Upload Content
                # FIX: Read into memory to avoid async/sync file handle issues with httpx
                with open(file_path, "rb") as f:
                    video_bytes = f.read()
                    
                upload_res = await client.put(upload_url, content=video_bytes)
                    
                if upload_res.status_code not in [200, 201]:
                    raise Exception(f"YouTube Upload Failed: {upload_res.text}")
                    
                result = upload_res.json()
                return result.get("id")

        finally:
            # Cleanup temp file if we created one
            if temp_file:
                TempFileManager.delete_file(temp_file)
