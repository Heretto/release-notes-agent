import logging
import sys
from typing import Any, Dict
import json
from datetime import datetime

class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_obj: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "extra"):
            log_obj.update(record.extra)
        
        return json.dumps(log_obj)

def setup_logging(level: str = "INFO") -> None:
    """Configure structured logging for the application."""
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )

    # SQLAlchemy logs every query at INFO when echo=True; keep it quiet unless
    # explicitly needed.
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    
    # Use JSON formatter in production
    from app.config import get_settings
    settings = get_settings()
    
    if settings.app_env == "production":
        formatter = JSONFormatter()
        for handler in logging.root.handlers:
            handler.setFormatter(formatter)