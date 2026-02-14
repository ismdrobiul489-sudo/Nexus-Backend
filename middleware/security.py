import os
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from services.logger_service import LoggerService

# Default key for development
DEFAULT_SECRET_KEY = "SECURE_AUTOMATION_APP_KEY_2025"

class SecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 1. Allow OPTIONS (CORS preflight) and Static files
        if request.method == "OPTIONS" or request.url.path.startswith("/static"):
             return await call_next(request)
             
        # 2. Allow Health Check for uptime monitors
        if request.url.path == "/health":
             return await call_next(request)

        # 3. Allow OAuth Callbacks (needs custom handling if secret is required, 
        # but usually callbacks are public/state-checked)
        if request.url.path == "/oauth-callback":
             return await call_next(request)
             
        # 4. Enforce Secret check for everything else (API and Screens)
        # Determine active key: .env overrides default
        env_key = os.getenv("APP_SECRET_KEY")
        active_key = env_key if env_key else DEFAULT_SECRET_KEY
        
        # Check for Header
        client_secret = request.headers.get("X-App-Secret")
        
        if client_secret != active_key:
             LoggerService.warn(f"🚫 Unauthorized Access Attempt to {request.url.path} from {request.client.host}")
             
             # Return JSON for API, HTML for Screens
             if request.url.path.startswith("/api"):
                 return JSONResponse(
                     status_code=403, 
                     content={"detail": "Unauthorized: Invalid or missing X-App-Secret header."}
                 )
             else:
                 from fastapi.responses import HTMLResponse
                 return HTMLResponse(
                     status_code=403,
                     content="<h1>403 Forbidden</h1><p>Public access to these screens is disabled. Please use the local Nexus ASM Dashboard.</p>"
                 )

        response = await call_next(request)
        return response
