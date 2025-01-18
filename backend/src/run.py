"""Script to run the FastAPI application with custom logging."""
import uvicorn
import logging
import os
from pathlib import Path
from config import setup_logging, get_log_file, get_or_create_log_file

def main():
    """Run the FastAPI application with custom logging."""
    # Get or create log file
    log_file = get_or_create_log_file()
    setup_logging()
    
    logger = logging.getLogger(__name__)
    logger.info(f"Using log file: {log_file}")
    logger.info("Starting FastAPI server")
    
    # Configure uvicorn with logging config
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )

if __name__ == "__main__":
    main() 