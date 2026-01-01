from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import Dict

from app.models.database import get_db
from app.config import get_settings

router = APIRouter()
settings = get_settings()

@router.get("/health")
async def health_check() -> Dict[str, str]:
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "environment": settings.app_env,
        "version": "1.0.0"
    }

@router.get("/health/db")
async def database_health(db: Session = Depends(get_db)) -> Dict[str, str]:
    """Check database connectivity."""
    try:
        # Simple query to test database connection
        db.execute("SELECT 1")
        return {"status": "healthy", "database": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "database": "disconnected", "error": str(e)}