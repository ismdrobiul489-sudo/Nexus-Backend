import httpx
import os
from typing import Dict, Any, Optional

class DailymotionBridgeService:
    def __init__(self):
        self.api_base = "https://api.dailymotion.com"
        self.auth_url = f"{self.api_base}/oauth/token"

    async def authenticate(self, client_id: str, client_secret: str, username: str, password: str) -> Dict[str, Any]:
        """
        authenticate: Exchange Username/Password for Access Token
        """
        data = {
            'grant_type': 'password',
            'client_id': client_id,
            'client_secret': client_secret,
            'username': username,
            'password': password,
            'scope': 'manage_videos userinfo'
        }
        
        async with httpx.AsyncClient() as client:
            resp = await client.post(self.auth_url, data=data)
            if resp.status_code != 200:
                error_data = resp.json()
                raise Exception(error_data.get('error_description') or error_data.get('error') or 'Dailymotion Authentication Failed')
            return resp.json()

    async def get_profile(self, access_token: str) -> Dict[str, Any]:
        """
        getProfile: Fetch user info (ID, name, avatar)
        """
        params = {
            'fields': 'id,username,avatar_720_url'
        }
        headers = {
            'Authorization': f'Bearer {access_token}'
        }
        
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self.api_base}/me", params=params, headers=headers)
            if resp.status_code != 200:
                raise Exception('Failed to fetch Dailymotion profile')
            
            data = resp.json()
            return {
                'id': data.get('id'),
                'name': data.get('username'),
                'avatar': data.get('avatar_720_url')
            }

    async def get_upload_url(self, access_token: str) -> str:
        """
        1. Get Upload URL
        """
        headers = {
            'Authorization': f'Bearer {access_token}'
        }
        async with httpx.AsyncClient() as client:
            resp = await client.get(f"{self.api_base}/file/upload", headers=headers)
            if resp.status_code != 200:
                error_data = resp.json()
                raise Exception(error_data.get('error', {}).get('message') or 'Failed to get DM upload URL')
            return resp.json().get('upload_url')

    async def upload_file(self, upload_url: str, file_path: str) -> str:
        """
        2. Upload File
        """
        if not os.path.exists(file_path):
            raise Exception(f"File not found: {file_path}")
            
        async with httpx.AsyncClient() as client:
            with open(file_path, 'rb') as f:
                files = {'file': f}
                resp = await client.post(upload_url, files=files)
                
            if resp.status_code >= 400:
                error_data = resp.json()
                raise Exception(error_data.get('error', {}).get('message') or 'Failed to upload video file')
            
            return resp.json().get('url')

    async def create_video(self, access_token: str, video_url: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        3. Create & Publish Video
        """
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/x-www-form-urlencoded',
        }
        
        data = {
            'url': video_url,
            'title': metadata.get('title'),
            'description': metadata.get('description', ''),
            'channel': metadata.get('channel', 'tech'),
            'published': 'true' if metadata.get('published') else 'false',
            'is_created_for_kids': 'false',
            'private': 'false'
        }
        
        if metadata.get('tags'):
            data['tags'] = metadata.get('tags')
            
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{self.api_base}/me/videos", headers=headers, data=data)
            if resp.status_code != 200:
                error_data = resp.json()
                raise Exception(error_data.get('error', {}).get('message') or 'Failed to create video on DM')
            return resp.json()
