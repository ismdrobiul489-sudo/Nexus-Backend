import asyncio
import os
from typing import Dict, Any, Optional
from services.facebook import FacebookService
from services.youtube import YouTubeService
from services.x import XService
from services.dailymotion_bridge import DailymotionBridgeService
from urllib.parse import quote

class SocialMediaService:
    @classmethod
    async def validate_connection(cls, platform: str, credentials: Dict[str, Any]) -> bool:
        p = platform.upper()
        
        if p == "FACEBOOK":
            return await FacebookService.verify_credentials(
                credentials.get("page_id") or credentials.get("pageId"), 
                credentials.get("access_token") or credentials.get("accessToken")
            )
        
        # Parity: TS mocks X and YouTube for now
        if p in ["X", "YOUTUBE", "INSTAGRAM", "TIKTOK"]:
            return await cls.mock_validation(credentials)

        if p == "DAILYMOTION":
            dm = DailymotionBridgeService()
            await dm.authenticate(
                credentials.get("api_key") or credentials.get("apiKey"),
                credentials.get("api_secret") or credentials.get("apiSecret"),
                credentials.get("username"),
                credentials.get("password")
            )
            return True
            
        return await cls.mock_validation(credentials)

    @classmethod
    async def fetch_account_profile(cls, platform: str, credentials: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        # Simulate network delay to match TS parity
        await asyncio.sleep(1)
        
        p = platform.upper()
        identifier = credentials.get("page_id") or credentials.get("handle") or credentials.get("username") or "Social Account"

        if p == "FACEBOOK":
            try:
                return await FacebookService.fetch_profile(
                    credentials.get("page_id") or credentials.get("pageId"), 
                    credentials.get("access_token") or credentials.get("accessToken")
                )
            except Exception as e:
                print(f"[SocialMediaService] FB Profile Error: {e}")

        # Default/Fallback for X and others (Mirroring TS avatars API logic)
        bg = "000000" if p == "X" else "1877F2" if p == "FACEBOOK" else "random"
        color = "fff"
        
        return {
            "accountName": f"{p.capitalize()} ({identifier})",
            "profilePictureUrl": f"https://ui-avatars.com/api/?name={quote(identifier)}&background={bg}&color={color}&size=128"
        }

    @classmethod
    async def publish(
        cls, 
        platform: str, 
        credentials: Dict[str, Any], 
        caption: str, 
        media_path: Optional[str] = None,
        video_type: str = "regular",
        video_title: str = "Untitled"
    ) -> Dict[str, Any]:
        p = platform.upper()
        
        if p == "FACEBOOK":
            page_id = credentials.get("page_id") or credentials.get("pageId")
            access_token = credentials.get("access_token") or credentials.get("accessToken")
            
            if not page_id or not access_token:
                raise Exception("Facebook Page ID and Access Token are required for publishing")

            # Determine Media Type
            if not media_path:
                # Text post
                return await FacebookService.publish_text(page_id, access_token, caption)
            
            # Per User Request: Use standard /videos endpoint for ALL video content
            is_video = False
            ext = os.path.splitext(media_path)[1].lower()
            is_video = ext in [".mp4", ".mov", ".avi", ".mkv", ".webm"] or "video" in media_path.lower() or video_type in ["reel", "video"]
            
            if is_video:
                # Standard Video API (/videos)
                video_id = await FacebookService.upload_video(page_id, access_token, media_path, video_title, caption)
                return {"id": video_id}
            else:
                # Default to photo for image-like or unknown
                return await FacebookService.upload_photo(page_id, access_token, media_path, caption)


        elif p == "YOUTUBE":
            # Extract OAuth Creds
            client_id = credentials.get("client_id") or credentials.get("clientId")
            client_secret = credentials.get("client_secret") or credentials.get("clientSecret")
            refresh_token = credentials.get("refresh_token") or credentials.get("refreshToken")
            
            if not client_id or not client_secret or not refresh_token:
                raise Exception("YouTube requires Client ID, Secret, and Refresh Token")
                
            # Metadata construction
            metadata = {
                "title": video_title,
                "description": caption,
                "privacy": "public", # Default to public per user feedback
                "categoryId": "22", # People & Blogs
                "tags": ["AI", "Shorts", "Automation"]
            }
            
            # YouTubeService handles URL download internally
            video_id = await YouTubeService.upload_video(client_id, client_secret, refresh_token, media_path, metadata)
            return {"id": video_id}

        raise Exception(f"Publishing to {p} is not yet implemented in backend.")

    @classmethod
    async def mock_validation(cls, credentials: Dict[str, Any]) -> bool:
        # Simulate network request
        await asyncio.sleep(1.5)
        
        token = credentials.get("access_token") or credentials.get("api_key")
        if not token or len(token) < 5:
            return False
            
        return True
