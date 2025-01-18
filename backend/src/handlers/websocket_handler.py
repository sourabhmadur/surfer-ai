"""WebSocket handler for browser automation."""
from typing import Dict, Any
from fastapi import APIRouter, WebSocket
from starlette.websockets import WebSocketState, WebSocketDisconnect
import logging
from handlers.base_handler import BaseHandler

# Get logger with the full module path
logger = logging.getLogger("src.handlers.websocket_handler")

router = APIRouter()

class WebSocketHandler(BaseHandler):
    """Handles WebSocket connections and message routing."""
    
    def __init__(self, websocket: WebSocket):
        super().__init__()
        self.websocket = websocket
        logger.info("WebSocket handler initialized")

    async def handle_connection(self):
        """Handle new WebSocket connection."""
        logger.info("New WebSocket connection received")
        await self.websocket.accept()
        logger.info("WebSocket connection accepted")

    async def handle_message(self, message: Dict[str, Any]):
        """Route and handle incoming messages."""
        try:
            logger.info("\n=== ENTERING handle_message ===")
            
            # Create a clean version of the message for logging
            if isinstance(message, dict):
                log_message = {}
                for key, value in message.items():
                    if key == 'data' and isinstance(value, dict):
                        log_message['data'] = {
                            k: '[SKIPPED]' if k in ['html', 'screenshot'] else v
                            for k, v in value.items()
                        }
                    elif key in ['html', 'screenshot', 'page_state']:
                        log_message[key] = '[REDACTED]'
                    else:
                        log_message[key] = value

            logger.info(f"Message type: {type(message)}")
            logger.info(f"Message content (sensitive data redacted): {log_message}")
            logger.info(f"Message keys: {message.keys() if isinstance(message, dict) else 'Not a dict'}")
            
            if not isinstance(message, dict):
                logger.error(f"Invalid message format. Expected dict, got {type(message)}")
                await self._send_error("Invalid message format")
                return

            # Determine message type
            message_type = message.get("type")
            if not message_type and "goal" in message:
                message_type = "goal"
                logger.info("No type specified, but found goal field. Setting type to 'goal'")

            logger.info(f"Processing message of type: {message_type}")

            # Get appropriate handler
            if message_type == "test":
                await self._send_message({
                    "type": "test",
                    "data": "Connection test successful"
                })
            elif message_type == "goal":
                result = await self.handle_goal(
                    goal=message.get("goal", ""),
                    screenshot=message.get("screenshot", ""),
                    html=message.get("html", ""),
                    session_id=message.get("session_id", 0)
                )
                await self._handle_result(result)
            else:
                result = await self.handle_action_result(message)
                await self._handle_result(result)

        except Exception as e:
            logger.error(f"Error handling message: {str(e)}", exc_info=True)
            await self._send_error(f"Error handling message: {str(e)}")

    async def cleanup(self):
        """Clean up resources when connection is closed."""
        try:
            if self.websocket.client_state == WebSocketState.CONNECTED:
                await self.websocket.close()
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}", exc_info=True)
        finally:
            # Reset state only when connection is closed
            self._reset_state()

    async def _send_message(self, message: Dict[str, Any]):
        """Send message to client."""
        try:
            if self.websocket.client_state == WebSocketState.CONNECTED:
                await self.websocket.send_json(message)
        except Exception as e:
            logger.error(f"Error sending message: {str(e)}", exc_info=True)

    async def _send_error(self, error_msg: str):
        """Send error message to client."""
        await self._send_message({
            "type": "error",
            "data": f"Error: {error_msg}"
        })

    async def _handle_result(self, result: Dict[str, Any]):
        """Handle and send result to client."""
        if not result.get("success", False):
            await self._send_error(result.get("error", "Unknown error occurred"))
            return

        if result["type"] == "action":
            await self._send_message({
                "type": "action",
                "data": result.get("data", {})
            })
        elif result["type"] == "complete":
            await self._send_message({
                "type": "complete",
                "data": result.get("data", "Task completed"),
                "message": result.get("message", "Task completed successfully")
            })
        else:
            await self._send_error(f"Unknown result type: {result['type']}")

@router.websocket("/agent")
async def agent_endpoint(websocket: WebSocket):
    """WebSocket endpoint for agent communication."""
    handler = WebSocketHandler(websocket)
    
    try:
        await handler.handle_connection()
        
        while True:
            try:
                message = await websocket.receive_json()
                await handler.handle_message(message)
            except WebSocketDisconnect:
                logger.info("WebSocket disconnected")
                break
            except Exception as e:
                logger.error(f"Error handling message: {str(e)}", exc_info=True)
                await handler.handle_error(str(e))
    finally:
        logger.info("Cleaning up WebSocket connection")
        await handler.cleanup() 