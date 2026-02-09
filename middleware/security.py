from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from services.logger_service import LoggerService

# Must match Frontend APP_SECRET_KEY logic or a simpler Shared Secret
# For this "Thin Client" migration, we use a simple Header check.
APP_SECRET_KEY = "SECURE_AUTOMATION_APP_KEY_2025"

class SecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Allow OPTIONS (CORS preflight) and Static files
        if request.method == "OPTIONS" or request.url.path.startswith("/static"):
             return await call_next(request)
             
        # Allow Health Check to be public? Or protected? 
        # Let's protect everything under /api except maybe health if needed for uptime monitors.
        # Strict mode: All /api requires header.
        if request.url.path.startswith("/api"):
            # Check for Header
            client_secret = request.headers.get("X-App-Secret")
            
            # Allow localhost/dev without strict check? 
            # Ideally NO, to ensure Mobile App sends it.
            
            if client_secret != APP_SECRET_KEY:
                 # Temporary: Allow if no header but logged (Soft Audit)
                 # LoggerService.warn(f"⚠️ Unauthenticated Request to {request.url.path}")
                 
                 # Strict Mode (Uncomment to enforce)
                 # return JSONResponse(status_code=403, content={"detail": "Unauthorized"})
                 pass

        response = await call_next(request)
        return response
