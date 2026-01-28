"""Uvicorn server entry point for FastAPI application."""
import uvicorn
import os
import logging
from dotenv import load_dotenv

load_dotenv()

# Configure logging before starting server
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    force=True
)

if __name__ == "__main__":
    # Get port from environment or default to 8000
    port = int(os.getenv("PORT", 8000))
    host = os.getenv("HOST", "0.0.0.0")
    
    # Configure uvicorn to use our logging configuration
    log_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                "datefmt": "%Y-%m-%d %H:%M:%S",
            },
        },
        "handlers": {
            "default": {
                "formatter": "default",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
            },
        },
        "root": {
            "level": "INFO",
            "handlers": ["default"],
        },
        "loggers": {
            "app": {
                "level": "INFO",
                "handlers": ["default"],
                "propagate": False,
            },
        },
    }
    
    uvicorn.run(
        "app.api.main:app",
        host=host,
        port=port,
        reload=True,  # Enable auto-reload for development
        log_level="info",
        log_config=log_config
    )

