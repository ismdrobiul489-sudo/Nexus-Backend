import httpx
import os

class DailymotionService:
    @staticmethod
    async def authenticate(client_id: str, client_secret: str, username: str, password: str) -> dict:
        url = "https://api.dailymotion.com/oauth/token"
        data = {
            "grant_type": "password",
            "client_id": client_id,
            "client_secret": client_secret,
            "username": username,
            "password": password,
            "scope": "manage_videos userinfo"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(url, data=data)
            if response.status_code != 200:
                raise Exception(f"DM Auth Failed: {response.text}")
            return response.json()

    @staticmethod
    async def get_upload_url(access_token: str) -> str:
        url = "https://api.dailymotion.com/file/upload"
        headers = {"Authorization": f"Bearer {access_token}"}
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers)
            if response.status_code != 200:
                raise Exception(f"DM Upload URL Failed: {response.text}")
            return response.json()["upload_url"]

    @staticmethod
    async def upload_file(upload_url: str, file_path: str) -> str:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
            
        async with httpx.AsyncClient() as client:
            with open(file_path, "rb") as f:
                files = {"file": f}
                response = await client.post(upload_url, files=files)
                
            if response.status_code != 200:
                raise Exception(f"DM Upload Failed: {response.text}")
            return response.json()["url"]

    @staticmethod
    async def create_video(access_token: str, video_url: str, title: str, description: str, tags: str = None, channel: str = "tech", published: bool = True) -> dict:
        url = "https://api.dailymotion.com/me/videos"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        data = {
            "url": video_url,
            "title": title,
            "description": description or "",
            "channel": channel,
            "published": "true" if published else "false",
            "is_created_for_kids": "false",
            "private": "false"
        }
        if tags:
            data["tags"] = tags
            
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, data=data)
            if response.status_code != 200:
                raise Exception(f"DM Create Failed: {response.text}")
            return response.json()
