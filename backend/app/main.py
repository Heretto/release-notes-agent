from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
import logging

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import get_settings
from app.api.routes import auth, credentials, instructions, jobs, webhooks, health, admin, account, organizations, invitations, superadmin
from app.core.logging import setup_logging
from app.core.rate_limit import limiter
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

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-CSRF-Token"],
)

# CSRF protection (double-submit cookie pattern)
from app.core.csrf import CSRFMiddleware
app.add_middleware(CSRFMiddleware)

# Include routers
app.include_router(health.router, prefix=settings.api_prefix, tags=["health"])
app.include_router(auth.router, prefix=settings.api_prefix, tags=["auth"])
app.include_router(invitations.router, prefix=settings.api_prefix, tags=["invitations"])
app.include_router(credentials.router, prefix=settings.api_prefix, tags=["credentials"])
app.include_router(instructions.router, prefix=settings.api_prefix, tags=["instructions"])
app.include_router(jobs.router, prefix=settings.api_prefix, tags=["jobs"])
app.include_router(webhooks.router, prefix=settings.api_prefix, tags=["webhooks"])
app.include_router(account.router, prefix=settings.api_prefix, tags=["account"])
app.include_router(organizations.router, prefix=settings.api_prefix, tags=["organizations"])
app.include_router(superadmin.router, prefix=settings.api_prefix, tags=["superadmin"])

# Admin routes (development only)
if settings.app_env == "development":
    app.include_router(admin.router, prefix=settings.api_prefix, tags=["admin"])

@app.get("/")
async def root():
    return {"message": "AI Release Notes Agent API", "version": "1.0.0"}