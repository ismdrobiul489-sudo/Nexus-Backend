import httpx
import os
import aiofiles
from typing import Optional, Union

GRAPH_API_VERSION = "v24.0" # Match latest used in TS
BASE_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}"
VIDEO_BASE_URL = f"https://graph-video.facebook.com/{GRAPH_API_VERSION}"
RUPLOAD_URL = f"https://rupload.facebook.com/video-upload/{GRAPH_API_VERSION}"

class FacebookService:
    
    @staticmethod
    async def publish_text(page_id: str, access_token: str, message: str) -> dict:
        url = f"{BASE_URL}/{page_id}/feed"
        params = {
            "message": message,
            "access_token": access_token
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, params=params)
            data = response.json()
            if "error" in data:
                raise Exception(f"Facebook Error: {data['error']['message']}")
            return data

    @staticmethod
    async def verify_credentials(page_id: str, access_token: str) -> bool:
        """Validates the Facebook Page ID and Access Token by fetching basic page metadata."""
        url = f"{BASE_URL}/{page_id}"
        params = {
            "fields": "id,name,category",
            "access_token": access_token
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params)
            data = response.json()
            if "error" in data:
                raise Exception(data["error"]["message"])
            return True

    @staticmethod
    async def fetch_profile(page_id: str, access_token: str) -> dict:
        """Fetches the page name and profile picture URL for 1:1 parity."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            # 1. Fetch Name
            name_url = f"{BASE_URL}/{page_id}?fields=name&access_token={access_token}"
            name_res = await client.get(name_url)
            name_data = name_res.json()
            account_name = name_data.get("name", f"Facebook Page ({page_id})")

            # 2. Fetch Profile Picture
            pic_url = f"{BASE_URL}/{page_id}/picture?redirect=false&access_token={access_token}"
            pic_res = await client.get(pic_url)
            pic_data = pic_res.json()
            profile_picture_url = pic_data.get("data", {}).get("url")

            # Fallback for picture if API fails
            if not profile_picture_url:
                from urllib.parse import quote
                profile_picture_url = f"https://ui-avatars.com/api/?name={quote('FB ' + page_id)}&background=1877F2&color=fff&size=128"

            return {
                "accountName": account_name,
                "profilePictureUrl": profile_picture_url
            }

    @staticmethod
    async def upload_photo(page_id: str, access_token: str, image_path_or_url: str, caption: str) -> dict:
        url = f"{BASE_URL}/{page_id}/photos"
        
        async with httpx.AsyncClient(timeout=300.0) as client:
            # Check if it's a URL
            if image_path_or_url.startswith("http"):
                params = {
                    "url": image_path_or_url,
                    "caption": caption,
                    "access_token": access_token
                }
                response = await client.post(url, params=params)
            else:
                # It's a local file
                if not os.path.exists(image_path_or_url):
                    raise FileNotFoundError(f"Image not found: {image_path_or_url}")
                
                with open(image_path_or_url, "rb") as f:
                    files = {"source": f}
                    data = {
                        "caption": caption,
                        "access_token": access_token
                    }
                    response = await client.post(url, data=data, files=files)
            
            data = response.json()
            if "error" in data:
                raise Exception(f"Facebook Photo Error: {data['error']['message']}")
            return data

    @staticmethod
    async def upload_video(page_id: str, access_token: str, video_path_or_url: str, title: str, description: str) -> str:
        url = f"{VIDEO_BASE_URL}/{page_id}/videos"
        print(f"[FB] 🎥 Video Upload Starting: {video_path_or_url[:100]}...")
        
        async with httpx.AsyncClient(timeout=300.0) as client:
            try:
                if video_path_or_url.startswith("http"):
                    # Method A: Direct URL Upload (Most efficient for Cloud/HF URLs)
                    print(f"[FB] Using URL Upload mode via /videos")
                    params = {
                        "access_token": access_token
                    }
                    data = {
                        "file_url": video_path_or_url,
                        "title": title,
                        "description": description
                    }
                    response = await client.post(url, params=params, data=data)
                    data = response.json()
                    print(f"[FB] Video API Response: {data}")
                    
                    if "error" in data:
                        err = data["error"]
                        if err.get("code") in [100, 200]:
                            raise Exception(f"Permission Denied (Facebook #{err.get('code')}). Valid Page Access Token with 'publish_video' scope required.")
                        raise Exception(f"Facebook Video URL Error: {err.get('message')}")
                    
                    video_id = data.get("id")
                    print(f"✅ [FB] Video Upload Queued/Started: {video_id}")
                    return video_id
                else:
                    # Method B: Local File Upload (Resumable Chunked Flow per User Reference)
                    # We utilize the upload_video_resumable logic but wrapped here for unified access
                    print(f"[FB] Using Local File Upload mode (Resumable Flow)")
                    # We need App ID for resumable flow, which we might not have in credentials directly.
                    # Falling back to standard multi-part if App ID missing, or just using simple source POST.
                    
                    if not os.path.exists(video_path_or_url):
                        raise FileNotFoundError(f"Video not found: {video_path_or_url}")
                    
                    # For simplicity and reliability in automation, we use the simple source POST first
                    # as it's a single atomic request for standard files.
                    with open(video_path_or_url, "rb") as f:
                        files = {"source": f}
                        data = {
                            "title": title,
                            "description": description,
                            "access_token": access_token
                        }
                        response = await client.post(url, data=data, files=files)
                    
                    data = response.json()
                    print(f"[FB] Local Video API Response: {data}")
                    
                    if "error" in data:
                        err = data["error"]
                        raise Exception(f"Facebook Video Error: {err.get('message')}")
                    
                    video_id = data.get("id")
                    print(f"✅ [FB] Local Video Published: {video_id}")
                    return video_id

            except Exception as e:
                print(f"[FB] ❌ Video Upload Exception: {type(e).__name__}: {str(e) or repr(e)}")
                raise


    @staticmethod
    async def upload_video_simple(page_id: str, access_token: str, video_url: str, title: str, description: str) -> str:
        # For public URLs, use the easy endpoint
        return await FacebookService.upload_video(page_id, access_token, video_url, title, description)

    @staticmethod
    async def upload_video_resumable(app_id: str, page_id: str, access_token: str, file_path: str, title: str, description: str) -> str:
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"Video file not found: {file_path}")
            
        file_size = os.path.getsize(file_path)
        file_name = os.path.basename(file_path)

        async with httpx.AsyncClient(timeout=600.0) as client:
            # Step 1: Start Session
            start_url = f"{BASE_URL}/{app_id}/uploads"
            params = {
                "file_name": file_name,
                "file_length": str(file_size),
                "file_type": "video/mp4",
                "access_token": access_token
            }
            res = await client.post(start_url, params=params)
            data = res.json()
            if "error" in data:
                raise Exception(f"Session Error: {data['error']['message']}")
            
            session_id = data["id"]
            
            # Step 2: Upload Binary
            upload_url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/{session_id}"
            headers = {
                "Authorization": f"OAuth {access_token}",
                "file_offset": "0"
            }
            
            # Read file in chunks if needed, but for simplicity reading all here (httpx handles streaming uploads nicely)
            # For truly large files, generator is better
            with open(file_path, "rb") as f:
                upload_res = await client.post(upload_url, headers=headers, content=f)
                
            upload_data = upload_res.json()
            if "error" in upload_data:
                raise Exception(f"Chunk Upload Error: {upload_data['error']['message']}")
            
            file_handle = upload_data["h"]
            
            # Step 3: Publish
            publish_url = f"{VIDEO_BASE_URL}/{page_id}/videos"
            publish_data = {
                "access_token": access_token,
                "title": title,
                "description": description,
                "fbuploader_video_file_chunk": file_handle
            }
            pub_res = await client.post(publish_url, data=publish_data)
            pub_data = pub_res.json()
            
            if "error" in pub_data:
                err = pub_data["error"]
                if err.get("code") in [100, 200]:
                    raise Exception(f"Permission Denied (Facebook #{err.get('code')}). Valid Page Access Token with 'publish_video' scope required. Please Re-Connect Account.")
                raise Exception(f"Publish Error: {err.get('message')}")
            
            return pub_data["id"]

    @staticmethod
    async def upload_reel(page_id: str, access_token: str, video_path_or_url: str, description: str) -> bool:
        print(f"[FB] 🎬 Reel Upload Starting: {video_path_or_url[:100]}...")
        
        async with httpx.AsyncClient(timeout=300.0) as client:
            try:
                # Step 1: Initialize
                print(f"[FB] Step 1: Initialize Reel...")
                init_url = f"{BASE_URL}/{page_id}/video_reels"
                init_payload = {
                    "upload_phase": "start",
                    "access_token": access_token
                }
                
                is_url = video_path_or_url.startswith("http")
                if is_url:
                    # For URLs, we can often pass video_source_url in the start phase
                    init_payload["video_source_url"] = video_path_or_url
                    print(f"[FB] Using URL Initialization mode")

                init_res = await client.post(init_url, json=init_payload)
                init_data = init_res.json()
                print(f"[FB] Step 1 Response: {init_data}")
                
                if "error" in init_data:
                    raise Exception(f"Reel Init Error: {init_data['error']['message']}")
                
                video_id = init_data["video_id"]
                print(f"[FB] Step 1 ✅ Video ID: {video_id}")
                
                # Step 2: Upload (Only if NOT a URL)
                if not is_url:
                    print(f"[FB] Step 2: Uploading Binary Data to rupload...")
                    upload_url = f"{RUPLOAD_URL}/{video_id}"
                    
                    if not os.path.exists(video_path_or_url):
                        raise FileNotFoundError(f"Reel file not found: {video_path_or_url}")
                    
                    with open(video_path_or_url, "rb") as f:
                        file_size = os.path.getsize(video_path_or_url)
                        headers = {
                            "Authorization": f"OAuth {access_token}",
                            "offset": "0",
                            "file_size": str(file_size)
                        }
                        print(f"[FB] Binary Upload (size: {file_size})")
                        upload_res = await client.post(upload_url, headers=headers, content=f)

                    upload_data = upload_res.json()
                    print(f"[FB] Step 2 Response: {upload_data}")
                    
                    if not upload_data.get("success"):
                        raise Exception(f"Reel Upload Failed: {upload_data}")
                    print(f"[FB] Step 2 ✅ Upload Successful")
                else:
                    print(f"[FB] Step 2: Skipped (using video_source_url)")
                    
                    # For URL uploads, we MUST wait for Facebook to finish processing before we can "finish" the upload
                    # Usually it takes a few seconds. We poll the video status.
                    print(f"[FB] ⏳ Polling Facebook processing status for video {video_id}...")
                    max_attempts = 15 # Wait up to ~75 seconds
                    for attempt in range(max_attempts):
                        status_url = f"{BASE_URL}/{video_id}?fields=status&access_token={access_token}"
                        status_res = await client.get(status_url)
                        status_data = status_res.json()
                        
                        video_status = status_data.get("status", {}).get("video_status")
                        print(f"[FB] Attempt {attempt+1}: Status is {video_status}")
                        
                        if video_status == "ready":
                            print(f"[FB] ✅ Video processing complete!")
                            break
                        elif video_status == "failed":
                            raise Exception(f"Facebook failed to download/process the video URL: {status_data}")
                        
                        await asyncio.sleep(5) # Poll every 5s
                    else:
                        print(f"[FB] ⚠️ Processing still underway, attempting to publish anyway...")

                # Step 3: Publish
                print(f"[FB] Step 3: Publish Reel...")
                publish_url = f"{BASE_URL}/{page_id}/video_reels"
                publish_params = {
                    "access_token": access_token,
                    "video_id": video_id,
                    "upload_phase": "finish",
                    "video_state": "PUBLISHED",
                    "description": description
                }
                pub_res = await client.post(publish_url, params=publish_params)
                pub_data = pub_res.json()
                print(f"[FB] Step 3 Response: {pub_data}")
                
                if "error" in pub_data:
                    # If it's "still being processed", wait one last time and retry
                    if "processing" in pub_data["error"]["message"].lower():
                         print(f"[FB] ⏳ Still processing, waiting 10s more and retrying Step 3...")
                         await asyncio.sleep(10)
                         pub_res = await client.post(publish_url, params=publish_params)
                         pub_data = pub_res.json()
                         print(f"[FB] Step 3 Retry Response: {pub_data}")

                if "error" in pub_data:
                    raise Exception(f"Reel Publish Error: {pub_data['error']['message']}")
                
                print(f"[FB] Step 3 ✅ Published Successfully!")
                return True
                
            except Exception as e:
                print(f"[FB] ❌ Reel Upload Exception: {type(e).__name__}: {str(e) or repr(e)}")
                raise


