from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.orm import Session
from typing import Dict
import logging

from app.models.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/health")
async def health_check() -> Dict[str, str]:
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "version": "1.0.0"
    }

@router.get("/health/db")
async def database_health(response: Response, db: Session = Depends(get_db)) -> Dict[str, str]:
    """Check database connectivity.

    Answers 503 when the probe fails — a 200 carrying "unhealthy" reads as healthy to
    every orchestrator and load balancer that only looks at the status code.
    """
    try:
        # SQLAlchemy 2.0 rejects raw strings — the probe must be wrapped in text().
        db.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        logger.error("Database health check failed: %s", e)
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "unhealthy", "database": "disconnected"}