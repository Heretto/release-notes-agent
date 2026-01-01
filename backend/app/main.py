from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from app.config import get_settings
from app.api.routes import auth, credentials, instructions, jobs, webhooks, health, admin, account
from app.core.logging import setup_logging
from app.models.database import init_db

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting up...")
    await init_db()
    yield
    # Shutdown
    logger.info("Shutting down...")

app = FastAPI(
    title="AI Release Notes Agent API",
    description="Automated DITA release notes generation from Jira tickets",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, prefix=settings.api_prefix, tags=["health"])
app.include_router(auth.router, prefix=settings.api_prefix, tags=["auth"])
app.include_router(credentials.router, prefix=settings.api_prefix, tags=["credentials"])
app.include_router(instructions.router, prefix=settings.api_prefix, tags=["instructions"])
app.include_router(jobs.router, prefix=settings.api_prefix, tags=["jobs"])
app.include_router(webhooks.router, prefix=settings.api_prefix, tags=["webhooks"])
app.include_router(account.router, prefix=settings.api_prefix, tags=["account"])

# Admin routes (development only)
if settings.app_env == "development":
    app.include_router(admin.router, prefix=settings.api_prefix, tags=["admin"])

@app.get("/")
async def root():
    return {"message": "AI Release Notes Agent API", "version": "1.0.0"}