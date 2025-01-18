"""Base handler for browser automation."""
from typing import Dict, Any, Optional
import logging
from models.base import BrowserState
from workflow import Agent, create_initial_state

# Get logger with the full module path
logger = logging.getLogger("src.handlers.base_handler")

class BaseHandler:
    """Base handler for browser automation requests."""
    
    def __init__(self):
        self.agent: Optional[Agent] = None
        self.state: Optional[BrowserState] = None

    async def handle_goal(self, goal: str, screenshot: str, html: str, session_id: int) -> Dict[str, Any]:
        """Handle new goal request."""
        try:
            logger.info(f"Creating state with goal: '{goal}'")
            
            # Initialize agent
            self.agent = Agent()
            
            # Create initial state and store it
            self.state = create_initial_state(
                goal=goal,
                screenshot=screenshot,
                html=html,
                session_id=session_id
            )
            
            # Add debug logging
            logger.info(f"State created with {len(self.state.past_actions)} past actions")
            logger.info(f"State has observations: {len(self.state.observations)}")
            
            # Execute workflow
            result = self.agent.execute(self.state)
            
            return result
            
        except Exception as e:
            logger.error(f"Error handling goal: {str(e)}", exc_info=True)
            raise

    async def handle_action_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Handle action result."""
        try:
            logger.info("\n=== ENTERING handle_action_result ===")
            
            # Create clean version of result for logging
            clean_result = {}
            if isinstance(result, dict):
                for key, value in result.items():
                    if key == 'data' and isinstance(value, dict):
                        clean_result['data'] = {
                            k: '[REDACTED]' if k in ['screenshot', 'html'] else v
                            for k, v in value.items()
                        }
                    elif key in ['screenshot', 'html']:
                        clean_result[key] = '[REDACTED]'
                    else:
                        clean_result[key] = value
            
            logger.info(f"Result received: {clean_result}")
            
            # Validate result format
            if not isinstance(result, dict):
                logger.error("Invalid result format: not a dictionary")
                return {
                    "success": False,
                    "error": "Invalid result format"
                }

            # Check for success field
            if "success" not in result:
                logger.error("Result missing success field")
                return {
                    "success": False,
                    "error": "Result missing success field"
                }

            # If success is false, handle error
            if not result["success"]:
                error_msg = result.get("error", "Unknown error occurred")
                return {
                    "success": False,
                    "error": error_msg
                }

            # For successful actions, expect data field
            if "data" not in result:
                logger.error("Successful result missing data field")
                return {
                    "success": False,
                    "error": "Result missing data field"
                }

            # Update state with new page state
            logger.info("Calling _update_state...")
            self._update_state(result)
            
            # Continue agent execution
            result = await self._execute_agent()
            return self._handle_agent_result(result)

        except Exception as e:
            logger.error(f"Error handling action result: {str(e)}", exc_info=True)
            return {
                "success": False,
                "error": f"Error handling action result: {str(e)}"
            }

    async def _execute_agent(self) -> Dict[str, Any]:
        """Execute next agent iteration."""
        if not self.state:
            logger.error("Cannot execute agent: state is None")
            raise ValueError("State not initialized")
            
        if not self.agent:
            logger.error("Cannot execute agent: agent is None")
            raise ValueError("Agent not initialized")
            
        # Log state before execution
        logger.info(f"State before execution - Goal: {self.state.goal}")
        logger.info(f"State has page_state: {bool(self.state.page_state)}")
        logger.info(f"Current observations: {len(self.state.observations)}")
        logger.info(f"Past actions: {len(self.state.past_actions)}")
        
        return self.agent.execute(self.state)

    def _handle_agent_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Handle agent execution result."""
        try:
            if not result.get("success", False):
                return {
                    "success": False,
                    "error": result.get("error", "Unknown error occurred")
                }

            if result["type"] == "action":
                # Make sure we have data and action fields
                if not result.get("data"):
                    return {
                        "success": False,
                        "error": "Missing data in action result"
                    }
                
                # Ensure action data is properly structured
                action_data = result["data"]
                if not isinstance(action_data, dict) or "action" not in action_data:
                    return {
                        "success": False,
                        "error": "Invalid action data structure"
                    }

                # Format the action data for state tracking
                if action_data["action"] == "click" and "element_data" in action_data:
                    # Include element description in past actions
                    element_desc = action_data["element_data"].get("description", "")
                    action_data["description"] = f"Clicked on: {element_desc}"
                elif action_data["action"] == "scroll":
                    direction = action_data.get("direction", "unknown")
                    pixels = action_data.get("pixels", 0)
                    action_data["description"] = f"Scrolled {direction} by {pixels} pixels"
                elif action_data["action"] == "type":
                    text = action_data.get("text", "")
                    action_data["description"] = f"Typed text: {text}"

                # Return properly structured response
                return {
                    "success": True,
                    "type": "action",
                    "data": action_data
                }
            elif result["type"] == "complete":
                self._reset_state()
                return {
                    "success": True,
                    "type": "complete",
                    "data": result.get("data", "Task completed"),
                    "message": result.get("message", "Task completed successfully")
                }
            else:
                return {
                    "success": False,
                    "error": f"Unknown result type: {result['type']}"
                }
        except Exception as e:
            logger.error(f"Error handling agent result: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    def _update_state(self, result: Dict[str, Any]) -> None:
        """Update state with new page state."""
        if not self.state:
            logger.error("Cannot update state: state is None")
            raise ValueError("State not initialized")
            
        if not isinstance(result, dict):
            logger.error(f"Invalid result type: {type(result)}")
            raise ValueError("Invalid result type")
            
        if "data" not in result:
            logger.error("Cannot update state: result missing data field")
            raise ValueError("Result missing data field")

        try:
            data = result["data"]
            logger.info("=== State Update Start ===")
            logger.info(f"Current state observations before update: {len(self.state.observations)}")
            logger.info(f"Current observation timestamps: {[obs.timestamp for obs in self.state.observations]}")
            logger.info(f"Data contains screenshot: {bool(data.get('screenshot'))}, html: {bool(data.get('html'))}")
            
            # Only update if we have valid data
            if data.get("screenshot") or data.get("html"):
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
            raise

    def _reset_state(self) -> None:
        """Reset agent and state."""
        self.agent = None
        self.state = None 