"""Main FastAPI application."""
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from handlers.websocket_handler import router as ws_router
from handlers.rest_handler import router as rest_router
from config import settings, setup_logging

# Set up logging once at application start
setup_logging()

# Get logger for this module
logger = logging.getLogger("src.main")
logger.info("FastAPI application starting...")

app = FastAPI(title="Browser Automation API")

@app.on_event("startup")
async def startup_event():
    """Log when the server starts."""
    logger.info("FastAPI server started")

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests."""
    logger.info(f"Incoming request: {request.method} {request.url}")
    try:
        response = await call_next(request)
        logger.info(f"Request completed: {request.method} {request.url} - Status: {response.status_code}")
        return response
    except Exception as e:
        logger.error(f"Request failed: {request.method} {request.url} - Error: {str(e)}")
        raise

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

logger.info("Configuring routes...")

# Include both WebSocket and REST routers
app.include_router(ws_router, prefix="/ws", tags=["websocket"])
app.include_router(rest_router, prefix="/api", tags=["rest"])

logger.info("Routes configured successfully")

@app.get("/")
async def root():
    """Root endpoint."""
    logger.info("Root endpoint accessed")
    return {
        "message": "Browser Automation API",
        "endpoints": {
            "websocket": "/ws/agent",
            "rest": {
                "goal": "/api/goal",
                "action_result": "/api/action_result"
            }
        }
    } 