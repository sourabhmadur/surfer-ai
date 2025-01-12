"""FastAPI application for browser automation."""
from fastapi import FastAPI, WebSocket
from starlette.middleware.cors import CORSMiddleware
from starlette.websockets import WebSocketDisconnect
from websocket_handler import WebSocketHandler
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

# Create logs directory if it doesn't exist
log_dir = Path(__file__).parent.parent / "logs"
log_dir.mkdir(exist_ok=True)

# Configure logging
log_file = log_dir / f"surfer_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

# Create a formatter
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Create and configure the file handler
file_handler = logging.FileHandler(log_file)
file_handler.setFormatter(formatter)
file_handler.setLevel(logging.INFO)

# Create and configure the stream handler
stream_handler = logging.StreamHandler()
stream_handler.setFormatter(formatter)
stream_handler.setLevel(logging.INFO)

# Configure the root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
root_logger.addHandler(file_handler)
root_logger.addHandler(stream_handler)

# Get logger for this module
logger = logging.getLogger(__name__)
logger.info(f"Logging to file: {log_file}")

# Set higher log levels for noisy libraries
logging.getLogger("uvicorn").setLevel(logging.WARNING)
logging.getLogger("uvicorn.error").setLevel(logging.WARNING)
logging.getLogger("fastapi").setLevel(logging.WARNING)
logging.getLogger("starlette").setLevel(logging.WARNING)

app = FastAPI()

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def clean_message_for_logging(message: Dict[str, Any]) -> Dict[str, Any]:
    """Clean sensitive or large content from messages for logging.
    
    Args:
        message: The original message dictionary
        
    Returns:
        A cleaned copy of the message with sensitive/large content replaced with [SKIPPED]
    """
    if not isinstance(message, dict):
        return message
        
    clean_message = {}
    for key, value in message.items():
        if key == 'data' and isinstance(value, dict):
            clean_message['data'] = {
                k: '[SKIPPED]' if k in ['html', 'screenshot'] else v
                for k, v in value.items()
            }
        elif key not in ['html', 'screenshot']:
            clean_message[key] = value
    return clean_message

@app.on_event("startup")
async def startup_event():
    """Run startup tasks."""
    logger.info("Starting application...")

@app.websocket("/ws/agent")
async def agent_endpoint(websocket: WebSocket):
    """WebSocket endpoint for agent communication."""
    handler = WebSocketHandler(websocket)
    
    try:
        await handler.handle_connection()
        
        while True:
            try:
                # Receive raw message without logging
                raw_message = await websocket.receive_json()
                # Clean and log message
                clean_message = clean_message_for_logging(raw_message)
                logger.debug(f"Received message: {clean_message}")
                await handler.handle_message(raw_message)
            except WebSocketDisconnect as e:
                logger.info(f"WebSocket disconnected with code {e.code}: {e.reason}")
                break
            except Exception as e:
                logger.error(f"Error handling message: {str(e)}", exc_info=True)
                await handler.handle_error(str(e))
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}", exc_info=True)
    finally:
        logger.info("Cleaning up WebSocket connection")
        await handler.cleanup() 