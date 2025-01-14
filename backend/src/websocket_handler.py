"""WebSocket handler for browser automation."""
from typing import Optional, Dict, Any
from fastapi import WebSocket
from starlette.websockets import WebSocketState
import logging
from workflow import Agent, create_initial_state
from models.base import Observation
import json

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
            handlers = {
                "test": self._handle_test_message,
                "goal": self._handle_goal_message
            }
            
            handler = handlers.get(message_type)
            if handler:
                logger.info(f"Found handler for message type: {message_type}")
                await handler(message)
            else:
                logger.info(f"No specific handler found for type {message_type}, treating as action result")
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
                await self._handle_agent_result(result)
            except Exception as e:
                logger.error(f"Error executing agent: {str(e)}", exc_info=True)
                await self._send_error(f"Error executing agent: {str(e)}")

        except Exception as e:
            logger.error(f"Error handling goal message: {str(e)}", exc_info=True)
            await self._handle_execution_error(e)

    async def _handle_action_result(self, message: Dict[str, Any]):
        """Handle action result message."""
        try:
            logger.info("\n=== ENTERING _handle_action_result ===")
            logger.info(f"Message received: {self._clean_data_for_logging(message)}")
            
            # Validate message format
            if not isinstance(message, dict):
                logger.error("Invalid message format: not a dictionary")
                return

            # Check for success field
            if "success" not in message:
                logger.error("Message missing success field")
                return

            # If success is false, handle error
            if not message["success"]:
                error_msg = message.get("error", "Unknown error occurred")
                await self._send_error(error_msg)
                return

            # For successful actions, expect data field
            if "data" not in message:
                logger.error("Successful message missing data field")
                return

            logger.info("=== State Before Update ===")
            logger.info(f"State exists: {self.state is not None}")
            if self.state:
                logger.info(f"Observations count: {len(self.state.observations)}")
                logger.info(f"Observation timestamps: {[obs.timestamp for obs in self.state.observations]}")

            # Update state with new page state
            logger.info("Calling _update_state...")
            self._update_state(message)
            
            logger.info("=== State After Update ===")
            logger.info(f"State exists: {self.state is not None}")
            if self.state:
                logger.info(f"Observations count: {len(self.state.observations)}")
                logger.info(f"Observation timestamps: {[obs.timestamp for obs in self.state.observations]}")
            
            # Continue agent execution
            result = await self._execute_agent()
            await self._handle_agent_result(result)

        except Exception as e:
            logger.error(f"Error handling action result: {str(e)}", exc_info=True)
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
        return result

    async def _handle_agent_result(self, result: Dict[str, Any]):
        """Handle agent execution result."""
        
        if not result.get("success", False):
            await self._send_error(result.get("error", "Unknown error occurred"))
            # Don't reset state on regular errors
            return

        if result["type"] == "action":
            # Get the action type from the result
            action_type = result.get("result", {}).get("action")
            logger.info(f"Processing action of type: {action_type}")

            if action_type == "fetch_user_details":
                # For fetch_user_details, we don't need to send to frontend
                # Just add the user details to the state and conversation
                if "user_details" in result["result"]:
                    user_details = result["result"]["user_details"]
                    
                    # Add user details to LLM conversation
                    user_details_message = {
                        "role": "assistant",
                        "content": f"I've fetched the user details. Here's the available information:\n{json.dumps(user_details, indent=2)}\nI'll use this information to fill out the form fields."
                    }
                    self.state.llm_conversation.append(user_details_message)
                    
                    # Continue agent execution
                    next_result = await self._execute_agent()
                    await self._handle_agent_result(next_result)
                    return

            # For other actions, send to frontend
            await self._send_action(result)
            
            # Wait for response from frontend
            try:
                logger.info("Waiting for response from frontend...")
                response = await self.websocket.receive_json()
                logger.info("Raw response received from frontend")
                # Clean response before logging
                clean_response = self._clean_data_for_logging(response)
                logger.info(f"Received response from frontend: {clean_response}")
                
                if not response.get("success", False):
                    error_msg = response.get("details", {}).get("error", "Unknown error occurred")
                    await self._send_error(f"Action failed: {error_msg}")
                    return
                
                # Continue agent execution on success
                logger.info("Processing frontend response through _handle_action_result...")
                await self._handle_action_result(response)
                
            except Exception as e:
                logger.error(f"Error receiving response from frontend: {str(e)}")
                await self._send_error(f"Failed to get response from frontend: {str(e)}")
                return
                
        elif result["type"] == "complete":
            await self._send_completion(result)
            # Reset state only on successful completion
            self._reset_state()
        else:
            await self._send_error(f"Unknown result type: {result['type']}")
            # Don't reset state for unknown result types


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
        logger.info("\n=== ENTERING _update_state ===")
        logger.info(f"Message received: {self._clean_data_for_logging(message)}")
        
        if not self.state:
            logger.error("Cannot update state: state is None")
            return
        
        if "data" not in message:
            logger.error("Cannot update state: message missing data field")
            return

        try:
            data = message["data"]
            logger.info("=== State Update Start ===")
            logger.info(f"Current state observations before update: {len(self.state.observations)}")
            logger.info(f"Current observation timestamps: {[obs.timestamp for obs in self.state.observations]}")
            logger.info(f"Data contains screenshot: {bool(data.get('screenshot'))}, html: {bool(data.get('html'))}")
            
            # Only update if we have valid data
            if data.get("screenshot") or data.get("html"):
                # Log state before update
                logger.info("Updating page state...")
                
                # Use the page_state setter to update state
                self.state.page_state = {
                    "screenshot": data.get("screenshot", ""),
                    "html": data.get("html", "")
                }
                
                logger.info("=== State Update Complete ===")
                logger.info(f"New state observations count: {len(self.state.observations)}")
                logger.info(f"New observation timestamps: {[obs.timestamp for obs in self.state.observations]}")
                logger.info(f"State update successful: {bool(self.state.page_state)}")
            else:
                logger.warning("Skipping state update - no valid screenshot or HTML data")
        except Exception as e:
            logger.error(f"Error updating state: {str(e)}", exc_info=True)

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

    def _clean_data_for_logging(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Clean sensitive data before logging."""
        if not isinstance(data, dict):
            return data
            
        clean_data = {}
        for key, value in data.items():
            if isinstance(value, dict):
                clean_data[key] = self._clean_data_for_logging(value)
            elif key in ['html', 'screenshot', 'page_state']:
                clean_data[key] = '[REDACTED]'
            else:
                clean_data[key] = value
        return clean_data 