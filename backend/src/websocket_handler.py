"""WebSocket handler for browser automation."""
from typing import Optional, Dict, Any
from fastapi import WebSocket
from starlette.websockets import WebSocketState
import logging
from workflow import Agent, create_initial_state

logger = logging.getLogger(__name__)

class WebSocketHandler:
    """Handles WebSocket connections and message routing."""
    
    def __init__(self, websocket: WebSocket):
        self.websocket = websocket
        self.agent: Optional[Agent] = None
        self.state = None

    async def handle_connection(self):
        """Handle new WebSocket connection."""
        logger.info("New WebSocket connection received")
        await self.websocket.accept()

    async def handle_error(self, error_msg: str):
        """Handle errors during message processing."""
        try:
            if self.websocket.client_state == WebSocketState.CONNECTED:
                await self._send_error(error_msg)
        except Exception as e:
            logger.error(f"Error sending error message: {str(e)}", exc_info=True)
        finally:
            self._reset_state()

    async def cleanup(self):
        """Clean up resources when connection is closed."""
        try:
            if self.websocket.client_state == WebSocketState.CONNECTED:
                await self.websocket.close()
        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}", exc_info=True)
        finally:
            self._reset_state()

    async def handle_message(self, message: Dict[str, Any]):
        """Route and handle incoming messages."""
        try:
            # Create a clean version of the message for logging
            if isinstance(message, dict):
                log_message = {}
                for key, value in message.items():
                    if key == 'data' and isinstance(value, dict):
                        log_message['data'] = {
                            k: '[SKIPPED]' if k in ['html', 'screenshot'] else v
                            for k, v in value.items()
                        }
                    elif key not in ['html', 'screenshot']:
                        log_message[key] = value

            logger.debug("\n=== Message Received ===")
            logger.debug(f"Message type: {type(message)}")
            logger.debug(f"Message content: {log_message}")
            logger.debug(f"Message keys: {message.keys() if isinstance(message, dict) else 'Not a dict'}")
            logger.debug("=== End Message ===\n")
            
            if not isinstance(message, dict):
                logger.error(f"Invalid message format. Expected dict, got {type(message)}")
                await self._send_error("Invalid message format")
                return

            # Determine message type
            message_type = message.get("type")
            if not message_type and "goal" in message:
                message_type = "goal"
                logger.debug("No type specified, but found goal field. Setting type to 'goal'")

            logger.info(f"Processing message of type: {message_type}")

            # Get appropriate handler
            handlers = {
                "test": self._handle_test_message,
                "goal": self._handle_goal_message
            }
            
            handler = handlers.get(message_type)
            if handler:
                logger.debug(f"Found handler for message type: {message_type}")
                await handler(message)
            else:
                logger.debug("No specific handler found, treating as action result")
                await self._handle_action_result(message)

        except Exception as e:
            logger.error(f"Error handling message: {str(e)}", exc_info=True)
            await self._send_error(f"Error handling message: {str(e)}")

    async def _handle_test_message(self, message: Dict[str, Any]):
        """Handle test message."""
        logger.info("Received test message")
        await self.websocket.send_json({
            "type": "test",
            "data": "Connection test successful"
        })

    async def _handle_goal_message(self, message: Dict[str, Any]):
        """Handle new goal/task message."""
        try:
            logger.debug("\n=== Processing Goal Message ===")
            logger.debug(f"Goal: {message.get('goal')}")
            logger.debug(f"Session ID: {message.get('session_id')}")
            logger.debug("=== End Goal Message ===\n")
            
            # Validate required fields
            if not self._validate_goal_message(message):
                logger.error(f"Message validation failed. Message keys: {message.keys()}")
                await self._send_error("Missing required fields: goal and session_id")
                return

            # Get page state from message
            page_state = {
                "screenshot": message.get("screenshot", ""),
                "html": message.get("html", "")
            }

            # Initialize agent and state
            self.agent = Agent()
            logger.info(f"Creating state with goal: {message.get('goal')!r}")
            
            try:
                # Convert and validate goal
                goal = str(message.get("goal", "")).strip()
                if not goal:
                    raise ValueError("Goal is empty after conversion")
                    
                session_id = int(message["session_id"])
                logger.debug(f"Converted values - Goal: {goal!r}, Session ID: {session_id}")
                
                self.state = create_initial_state(
                    session_id=session_id,
                    goal=goal,
                    screenshot=page_state["screenshot"],
                    html=page_state["html"]
                )
                
                # Verify state was created correctly
                if not hasattr(self.state, 'goal') or not self.state.goal:
                    raise ValueError("State was created but goal is missing or empty")
                    
                logger.info(f"State created successfully with goal: {self.state.goal!r}")
            except Exception as e:
                logger.error(f"Error creating state: {str(e)}", exc_info=True)
                await self._send_error(f"Error creating state: {str(e)}")
                return

            # Execute agent
            try:
                logger.debug("Starting agent execution...")
                result = await self._execute_agent()
                logger.debug(f"Agent execution result: {result}")
                await self._handle_agent_result(result)
            except Exception as e:
                logger.error(f"Error executing agent: {str(e)}", exc_info=True)
                await self._send_error(f"Error executing agent: {str(e)}")

        except Exception as e:
            logger.error(f"Error handling goal message: {str(e)}", exc_info=True)
            await self._handle_execution_error(e)

    async def _handle_action_result(self, message: Dict[str, Any]):
        """Handle action result message."""
        if not self._validate_action_result(message):
            return

        try:
            # Update state with new page state
            self._update_state(message)
            
            # Continue agent execution
            result = await self._execute_agent()
            await self._handle_agent_result(result)

        except Exception as e:
            await self._handle_execution_error(e)

    async def _execute_agent(self) -> Dict[str, Any]:
        """Execute agent and return result."""
        if not self.agent:
            raise ValueError("Agent not initialized")
        if not self.state:
            raise ValueError("State not initialized")
            
        # Log state before execution
        logger.info(f"State before execution - Goal: {getattr(self.state, 'goal', None)}")
        logger.info(f"State has page_state: {hasattr(self.state, 'page_state')}")
        
        if not hasattr(self.state, 'goal') or not self.state.goal:
            raise ValueError("State missing goal")
        if not hasattr(self.state, 'page_state') or not self.state.page_state:
            raise ValueError("State missing page_state")
        
        logger.info(f"Executing agent with goal: {self.state.goal}")
        result = self.agent.execute(self.state)
        logger.info(f"Agent execution result: {result}")
        return result

    async def _handle_agent_result(self, result: Dict[str, Any]):
        """Handle agent execution result."""
        if not result.get("success", False):
            await self._send_error(result.get("error", "Unknown error occurred"))
            self._reset_state()
            return

        if result["type"] == "action":
            await self._send_action(result)
        elif result["type"] == "complete":
            await self._send_completion(result)
        else:
            await self._send_error(f"Unknown result type: {result['type']}")
            self._reset_state()

    async def _send_action(self, result: Dict[str, Any]):
        """Send action message to client."""
        await self.websocket.send_json({
            "type": "action",
            "data": result.get("result", {})
        })
        if "message" in result:
            await self.websocket.send_json({
                "type": "message",
                "data": result["message"]
            })

    async def _send_completion(self, result: Dict[str, Any]):
        """Send completion message to client."""
        await self.websocket.send_json({
            "type": "complete",
            "data": result.get("data", "Task completed"),
            "message": result.get("message", "Task completed successfully")
        })
        self._reset_state()

    async def _send_error(self, error_msg: str):
        """Send error message to client."""
        logger.error(f"Error: {error_msg}")
        await self.websocket.send_json({
            "type": "error",
            "data": f"Error: {error_msg}"
        })

    def _reset_state(self):
        """Reset agent and state."""
        self.agent = None
        self.state = None

    def _update_state(self, message: Dict[str, Any]):
        """Update state with new page state."""
        if not self.state:
            logger.error("Cannot update state: state is None")
            return
        
        if "data" not in message:
            logger.error("Cannot update state: message missing data field")
            return

        try:
            data = message["data"]
            self.state.page_state = {
                "screenshot": data.get("screenshot", ""),
                "html": data.get("html", "")
            }
            logger.info("State updated successfully")
        except Exception as e:
            logger.error(f"Error updating state: {str(e)}")

    @staticmethod
    def _validate_goal_message(message: Dict[str, Any]) -> bool:
        """Validate goal message fields."""
        if not isinstance(message, dict):
            return False
        
        required_fields = ["goal", "session_id"]
        has_required = all(field in message for field in required_fields)
        
        if not has_required:
            logger.error(f"Missing required fields in message: {message.keys()}")
            return False
            
        return True

    @staticmethod
    def _validate_action_result(message: Dict[str, Any]) -> bool:
        """Validate action result message."""
        return message.get("success") is not None 

    @staticmethod
    def _truncate_content(content: str, max_length: int = 100) -> str:
        """Truncate long content for logging."""
        if not content:
            return "[empty]"
        size_kb = len(content) / 1024
        if size_kb < 1:
            return f"[{len(content)}c]"  # Even more concise
        return f"[{size_kb:.1f}k]"  # Removed 'b' to be more concise 

    async def _handle_execution_error(self, error: Exception):
        """Handle execution errors by sending an error message to the client."""
        await self._send_error(f"Execution error: {str(error)}")

    async def _handle_error(self, error_message: str):
        """Handle errors by sending an error message to the client."""
        await self._send_message({
            "type": "error",
            "error": error_message
        }) 