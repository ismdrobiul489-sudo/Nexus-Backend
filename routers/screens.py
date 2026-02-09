from fastapi import APIRouter
from fastapi.responses import FileResponse

router = APIRouter()

@router.get("/")
@router.get("/home_screen")
async def home_screen():
    return FileResponse('templates/home_screen.html')

@router.get("/my_assistants_screen")
async def my_assistants_screen():
    return FileResponse('templates/my_assistants_screen.html')

@router.get("/rss_feed_screen")
async def rss_feed_screen():
    return FileResponse('templates/rss_feed_screen.html')

@router.get("/analytics_screen")
async def analytics_screen():
    return FileResponse('templates/analytics_screen.html')

@router.get("/flow_builder_screen")
async def flow_builder_screen():
    return FileResponse('templates/flow_builder_screen.html')

@router.get("/video_creator_screen")
async def video_creator_screen():
    return FileResponse('templates/video_creator_screen.html')

@router.get("/settings_screen")
async def settings_screen():
    return FileResponse('templates/settings_screen.html')

@router.get("/logs_screen")
async def logs_screen():
    return FileResponse('templates/logs_screen.html')

@router.get("/execution_logs_screen")
async def execution_logs_screen():
    return FileResponse('templates/execution_log_screen.html')

@router.get("/automation_screen")
async def automation_screen():
    return FileResponse('templates/automation_screen.html')

@router.get("/facebook_connect_screen")
async def facebook_connect_screen():
    return FileResponse('templates/facebook_connect_screen.html')

@router.get("/file_manager_screen")
async def file_manager_screen():
    return FileResponse('templates/file_manager_screen.html')

@router.get("/generator_screen")
async def generator_screen():
    return FileResponse('templates/manual_post_screen.html')

@router.get("/history_screen")
async def history_screen():
    return FileResponse('templates/history_screen.html')

@router.get("/news_trends_screen")
async def news_trends_screen():
    return FileResponse('templates/news_trends_screen.html')

@router.get("/auth/youtube/start")
async def youtube_auth_start(client_id: str, client_secret: str):
    """
    Start YouTube OAuth flow. Frontend calls this with client credentials.
    Redirects user to Google consent screen.
    """
    import urllib.parse
    
    # Store credentials in session (using query params for simplicity in callback)
    redirect_uri = "http://localhost:8000/oauth-callback"
    scopes = "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.readonly"
    
    # Build state with encoded credentials (for callback to use)
    import base64
    import json
    state_data = json.dumps({"client_id": client_id, "client_secret": client_secret})
    state = base64.urlsafe_b64encode(state_data.encode()).decode()
    
    auth_url = (
        f"https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={urllib.parse.quote(client_id)}&"
        f"redirect_uri={urllib.parse.quote(redirect_uri)}&"
        f"response_type=code&"
        f"scope={urllib.parse.quote(scopes)}&"
        f"access_type=offline&"
        f"prompt=consent&"
        f"state={state}"
    )
    
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url=auth_url)


@router.get("/oauth-callback")
async def oauth_callback(code: str = None, state: str = None, error: str = None):
    """
    Handle Google OAuth callback. Exchanges code for tokens server-side.
    Returns HTML page that sends tokens to opener via postMessage.
    """
    from fastapi.responses import Response
    import httpx
    import base64
    import json
    
    # Handle error from Google
    if error:
        html = f"""
        <!DOCTYPE html>
        <html>
        <head><title>OAuth Error</title></head>
        <body style="font-family: sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white;">
            <div style="text-align: center; padding: 40px; background: rgba(255,255,255,0.1); border-radius: 20px;">
                <div style="font-size: 64px;">❌</div>
                <h1>Authentication Failed</h1>
                <p>{error}</p>
                <script>
                    if (window.opener) {{
                        window.opener.postMessage({{ type: 'youtube_oauth_error', error: '{error}' }}, '*');
                        setTimeout(() => window.close(), 2000);
                    }}
                </script>
            </div>
        </body>
        </html>
        """
        return Response(content=html, media_type="text/html", headers={"Cross-Origin-Opener-Policy": "unsafe-none"})
    
    if not code or not state:
        html = """
        <!DOCTYPE html>
        <html>
        <head><title>OAuth Error</title></head>
        <body style="font-family: sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh;">
            <div style="text-align: center;">
                <h1>❌ Missing Parameters</h1>
                <p>No authorization code received.</p>
            </div>
        </body>
        </html>
        """
        return Response(content=html, media_type="text/html", headers={"Cross-Origin-Opener-Policy": "unsafe-none"})
    
    # Decode state to get credentials
    try:
        state_data = json.loads(base64.urlsafe_b64decode(state).decode())
        client_id = state_data["client_id"]
        client_secret = state_data["client_secret"]
    except Exception as e:
        html = f"""
        <!DOCTYPE html>
        <html>
        <head><title>OAuth Error</title></head>
        <body style="font-family: sans-serif; text-align: center; padding-top: 100px;">
            <h1>❌ Invalid State</h1>
            <p>Could not decode credentials: {str(e)}</p>
        </body>
        </html>
        """
        return Response(content=html, media_type="text/html", headers={"Cross-Origin-Opener-Policy": "unsafe-none"})
    
    # Exchange code for tokens
    redirect_uri = "http://localhost:8000/oauth-callback"
    token_url = "https://oauth2.googleapis.com/token"
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            token_response = await client.post(token_url, data={
                "client_id": client_id,
                "client_secret": client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code"
            })
            
            if token_response.status_code != 200:
                error_text = token_response.text
                html = f"""
                <!DOCTYPE html>
                <html>
                <head><title>Token Exchange Failed</title></head>
                <body style="font-family: sans-serif; text-align: center; padding-top: 100px; color: #333;">
                    <h1>❌ Token Exchange Failed</h1>
                    <p>{error_text[:500]}</p>
                    <script>
                        if (window.opener) {{
                            window.opener.postMessage({{ type: 'youtube_oauth_error', error: 'Token exchange failed' }}, '*');
                        }}
                    </script>
                </body>
                </html>
                """
                return Response(content=html, media_type="text/html", headers={"Cross-Origin-Opener-Policy": "unsafe-none"})
            
            tokens = token_response.json()
            access_token = tokens.get("access_token")
            refresh_token = tokens.get("refresh_token")
            
            # Fetch channel profile
            channel_info = {"id": "", "name": "YouTube Channel", "thumbnail": ""}
            try:
                print(f"[OAuth] Fetching channel profile with access_token: {access_token[:20]}...")
                profile_response = await client.get(
                    "https://www.googleapis.com/youtube/v3/channels?part=snippet&mine=true",
                    headers={"Authorization": f"Bearer {access_token}"}
                )
                print(f"[OAuth] Channel API response status: {profile_response.status_code}")
                if profile_response.status_code == 200:
                    profile_data = profile_response.json()
                    print(f"[OAuth] Channel API response: {profile_data}")
                    if profile_data.get("items"):
                        item = profile_data["items"][0]
                        channel_info = {
                            "id": item["id"],
                            "name": item["snippet"]["title"],
                            "thumbnail": item["snippet"]["thumbnails"]["default"]["url"]
                        }
                        print(f"[OAuth] Channel found: {channel_info['name']}, thumbnail: {channel_info['thumbnail']}")
                    else:
                        print(f"[OAuth] No items in channel response!")
                else:
                    print(f"[OAuth] Channel API error: {profile_response.text}")
            except Exception as profile_err:
                print(f"[OAuth] Failed to fetch channel profile: {profile_err}")
            
            # Calculate expiry timestamp
            import time
            expires_in = tokens.get("expires_in", 3600)  # Default 1 hour
            expiry_date = int(time.time() * 1000) + (expires_in * 1000)  # Milliseconds
            
            # Build success response with postMessage
            tokens_json = json.dumps({
                "access_token": access_token,
                "refresh_token": refresh_token,
                "client_id": client_id,
                "client_secret": client_secret,
                "expires_in": expires_in,
                "expiry_date": expiry_date
            })
            channel_json = json.dumps(channel_info)
            
            html = f"""
            <!DOCTYPE html>
            <html>
            <head><title>YouTube Connected!</title></head>
            <body style="font-family: sans-serif; display: flex; justify-content: center; align-items: center; height: 100vh; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; margin: 0;">
                <div style="text-align: center; padding: 40px; background: rgba(255,255,255,0.1); backdrop-filter: blur(10px); border-radius: 20px;">
                    <div style="font-size: 64px;">✅</div>
                    <h1 style="color: #4ade80;">Authentication Successful!</h1>
                    <p>Connected to: <strong>{channel_info['name']}</strong></p>
                    <p style="opacity: 0.8;">This window will close automatically...</p>
                </div>
                <script>
                    const tokens = {tokens_json};
                    const channel = {channel_json};
                    
                    if (window.opener) {{
                        window.opener.postMessage({{
                            type: 'youtube_oauth_success',
                            tokens: tokens,
                            channel: channel
                        }}, '*');
                        setTimeout(() => window.close(), 1500);
                    }} else {{
                        document.body.innerHTML += '<p>Please close this window manually.</p>';
                    }}
                </script>
            </body>
            </html>
            """
            return Response(content=html, media_type="text/html", headers={"Cross-Origin-Opener-Policy": "unsafe-none"})
            
        except httpx.TimeoutException:
            html = """
            <!DOCTYPE html>
            <html>
            <head><title>Timeout</title></head>
            <body style="font-family: sans-serif; text-align: center; padding-top: 100px;">
                <h1>⏱️ Request Timed Out</h1>
                <p>Please try again.</p>
            </body>
            </html>
            """
            return Response(content=html, media_type="text/html", headers={"Cross-Origin-Opener-Policy": "unsafe-none"})
        except Exception as e:
            html = f"""
            <!DOCTYPE html>
            <html>
            <head><title>Error</title></head>
            <body style="font-family: sans-serif; text-align: center; padding-top: 100px;">
                <h1>❌ Error</h1>
                <p>{str(e)}</p>
            </body>
            </html>
            """
            return Response(content=html, media_type="text/html", headers={"Cross-Origin-Opener-Policy": "unsafe-none"})
