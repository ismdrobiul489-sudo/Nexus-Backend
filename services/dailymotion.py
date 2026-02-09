import httpx
from typing import Dict, Any

class DailymotionService:
    @staticmethod
    async def verify_credentials(api_key: str, api_secret: str, username: str, password: str) -> bool:
        """Validates Dailymotion credentials by attempting to get an OAuth2 access token."""
        url = "https://api.dailymotion.com/oauth/token"
        data = {
            "grant_type": "password",
            "client_id": api_key,
            "client_secret": api_secret,
            "username": username,
            "password": password,
            "scope": "manage_videos"
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(url, data=data)
            if response.status_code != 200:
                res_data = response.json()
                error_msg = res_data.get("error_description", "Invalid Dailymotion credentials")
                raise Exception(error_msg)
            return True
