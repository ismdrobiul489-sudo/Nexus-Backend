import httpx
import os
import json
from authlib.integrations.httpx_client import OAuth1Client
from typing import Optional, Dict, Any

class XService:
    @staticmethod
    async def post_tweet(api_key: str, api_secret: str, access_token: str, access_token_secret: str, text: str, media_ids: list = None) -> Dict[str, Any]:
        url = "https://api.x.com/2/tweets"
        client = OAuth1Client(api_key, api_secret, access_token, access_token_secret)
        
        payload = {"text": text}
        if media_ids:
            payload["media"] = {"media_ids": media_ids}
            
        async with client:
            response = await client.post(url, json=payload)
            if response.status_code not in [200, 201]:
                raise Exception(f"X Post Failed: {response.text}")
            return response.json()

    @staticmethod
    async def verify_credentials(api_key: str, api_secret: str, access_token: str, access_token_secret: str) -> bool:
        """Validates X API credentials by fetching authenticated user details."""
        url = "https://api.x.com/2/users/me"
        client = OAuth1Client(api_key, api_secret, access_token, access_token_secret)
        async with client:
            response = await client.get(url)
            if response.status_code != 200:
                data = response.json()
                error_msg = data.get("detail", "Invalid Credentials")
                raise Exception(error_msg)
            return True

    @staticmethod
    async def upload_media(api_key: str, api_secret: str, access_token: str, access_token_secret: str, file_path: str) -> str:
        """Simple upload for images < 5MB"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
            
        url = "https://upload.twitter.com/1.1/media/upload.json"
        client = OAuth1Client(api_key, api_secret, access_token, access_token_secret)
        
        async with client:
            with open(file_path, "rb") as f:
                files = {"media": f}
                response = await client.post(url, files=files)
                
            if response.status_code != 200:
                raise Exception(f"X Media Upload Failed: {response.text}")
            
            data = response.json()
            return data["media_id_string"]

    @staticmethod
    async def upload_video(api_key: str, api_secret: str, access_token: str, access_token_secret: str, file_path: str) -> str:
        """Chunked upload for videos (Mirroring mobile's INIT -> APPEND -> FINALIZE)"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
            
        base_url = "https://upload.twitter.com/1.1/media/upload.json"
        client = OAuth1Client(api_key, api_secret, access_token, access_token_secret)
        file_size = os.path.getsize(file_path)
        
        async with client:
            # 1. INIT
            init_data = {
                "command": "INIT",
                "total_bytes": str(file_size),
                "media_type": "video/mp4",
                "media_category": "tweet_video"
            }
            res = await client.post(base_url, data=init_data)
            if res.status_code != 202:
                raise Exception(f"X Video INIT Failed: {res.text}")
            
            media_id = res.json()["media_id_string"]
            
            # 2. APPEND (For now simple single append if < 5MB or repeat, simplifying but following structure)
            chunk_size = 4 * 1024 * 1024 # 4MB
            with open(file_path, "rb") as f:
                segment_index = 0
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                        
                    append_data = {
                        "command": "APPEND",
                        "media_id": media_id,
                        "segment_index": str(segment_index)
                    }
                    # httpx OAuth1Client handles signing of data
                    res = await client.post(base_url, data=append_data, files={"media": chunk})
                    if res.status_code != 204:
                         raise Exception(f"X Video APPEND Failed: {res.text}")
                    
                    segment_index += 1
            
            # 3. FINALIZE
            finalize_data = {
                "command": "FINALIZE",
                "media_id": media_id
            }
            res = await client.post(base_url, data=finalize_data)
            if res.status_code != 201:
                raise Exception(f"X Video FINALIZE Failed: {res.text}")
                
            # 4. STATUS (Wait for processing)
            import asyncio
            for _ in range(12): # Max 2 mins
                status_res = await client.get(base_url, params={"command": "STATUS", "media_id": media_id})
                data = status_res.json()
                info = data.get("processing_info", {})
                state = info.get("state")
                
                if state == "succeeded":
                    return media_id
                elif state == "failed":
                    raise Exception(f"X Video Processing Failed: {info.get('error', {}).get('message')}")
                
                wait = info.get("check_after_secs", 5)
                await asyncio.sleep(wait)
                
            return media_id
