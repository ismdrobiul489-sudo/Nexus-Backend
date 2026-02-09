from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import os
from contextlib import asynccontextmanager
from database import init_db
from services.scheduler import SchedulerService
from services.logger_service import LoggerService

# Define Lifespan (Startup/Shutdown)
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Connect DB, Start Scheduler, Init Logger
    LoggerService.init()
    print("🚀 Nexus ASM Backend Starting...")
    await init_db()
    SchedulerService.start()
    await SchedulerService.reset_stuck_jobs()
    yield
    # Shutdown: Close connections
    print("🛑 Nexus ASM Backend Shutting Down...")

from routers import api

app = FastAPI(
    title="Nexus ASM Backend",
    description="Python Backend for Facebook Automation Assistant",
    version="1.0.0",
    lifespan=lifespan
)

# CORS (Allow frontend access)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allow all for local dev (React Native)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api.router)
from routers import sync, system
app.include_router(sync.router)
app.include_router(system.router)
from routers import monitoring
app.include_router(monitoring.router)

@app.get("/health")
async def root_health():
    return {"status": "online", "message": "Nexus ASM Backend is running"}

from middleware.security import SecurityMiddleware
app.add_middleware(SecurityMiddleware)

from middleware.request_logging import RequestLoggingMiddleware
app.add_middleware(RequestLoggingMiddleware)


from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

# ... (Previous API includes)

# Mount Static Files (CSS, JS)
app.mount("/static", StaticFiles(directory="static"), name="static")

from routers import screens

# Mount Screens Router
app.include_router(screens.router)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
