"""Handles execution of browser actions."""
import logging
import re
from typing import Dict, Any
from models.base import BrowserState
from tools.element_identifier import ElementIdentifier
from tools.user_details_fetcher import UserDetailsFetcher
from llm import LLMProvider

logger = logging.getLogger(__name__)

class ActionHandler:
    """Handler for browser actions."""
    
    def __init__(self, llm: LLMProvider):
        """Initialize action handler."""
        self.element_identifier = ElementIdentifier(llm)
        self.user_details_fetcher = UserDetailsFetcher()
    
    def handle_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Handle browser action."""
        try:
            # Log the action
            logger.info(f"=== Executing Action === {action['action']}")
            
            # Validate action format
            if not isinstance(action, dict) or "action" not in action:
                return {
                    "success": False,
                    "error": "Invalid action format"
                }

            # Execute action
            if action["action"] == "scroll":
                return self._handle_scroll(action)
            elif action["action"] == "click":
                return self._handle_click(action)
            elif action["action"] == "type":
                return self._handle_type(action)
            elif action["action"] == "keypress":
                return self._handle_keypress(action)
            elif action["action"] == "wait":
                return self._handle_wait(action)
            elif action["action"] == "complete":
                return self._handle_complete()
            else:
                return {
                    "success": False,
                    "error": f"Unknown action: {action['action']}"
                }
                
        except Exception as e:
            logger.error(f"Error handling action: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }

    def _handle_type(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Handle type actions."""
        try:
            # Validate required fields
            if "text" not in action:
                return self._handle_error("Missing required field 'text' for type action")

            text_to_type = action["text"]

            # Return properly structured response
            return {
                "success": True,
                "type": "action",
                "data": {
                    "action": "type",
                    "text": text_to_type
                }
            }
        except Exception as e:
            return self._handle_error(f"Error handling type action: {str(e)}")

    def _handle_click(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Handle click actions."""
        try:
            # Validate required fields
            if "element_data" not in action:
                return self._handle_error("Missing required field 'element_data' for click action")

            element_data = action["element_data"]
            if not isinstance(element_data, dict):
                return self._handle_error("element_data must be a dictionary")

            if "selector" not in element_data:
                return self._handle_error("Missing required field 'selector' in element_data")

            # Return click action with element data
            return {
                "success": True,
                "type": "action",
                "data": {
                    "action": "click",
                    "element_data": element_data
                }
            }
        except Exception as e:
            return self._handle_error(f"Error handling click action: {str(e)}")

    def _handle_scroll(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Handle scroll actions."""
        try:
            # Validate required fields
            if "direction" not in action:
                return self._handle_error("Missing required field 'direction' for scroll action")
            if "pixels" not in action:
                return self._handle_error("Missing required field 'pixels' for scroll action")

            direction = action["direction"].lower()
            pixels = int(action["pixels"])

            if direction not in ["up", "down"]:
                return self._handle_error(f"Invalid scroll direction: {direction}. Must be 'up' or 'down'")

            # Return scroll action without needing page state
            return {
                "success": True,
                "type": "action",
                "data": {
                    "action": "scroll",
                    "direction": direction,
                    "pixels": pixels
                }
            }
        except Exception as e:
            return self._handle_error(f"Error handling scroll action: {str(e)}")

    def _handle_keypress(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Handle keypress actions."""
        try:
            # Validate required fields
            if "key" not in action:
                return self._handle_error("Missing required field 'key' for keypress action")

            key = action["key"].lower()
            valid_keys = ["enter", "tab", "escape"]
            
            if key not in valid_keys:
                return self._handle_error(f"Invalid key: {key}. Valid keys are: {', '.join(valid_keys)}")

            # Return properly structured response
            return {
                "success": True,
                "type": "action",
                "data": {
                    "action": "keypress",
                    "key": key
                }
            }
        except Exception as e:
            return self._handle_error(f"Error handling keypress action: {str(e)}")

    def _handle_fetch_user_details(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Handle fetch user details action."""
        try:
            result = self.user_details_fetcher.fetch_details()

            if not result["success"]:
                return self._handle_error(result["error"])

            return {
                "success": True,
                "type": "action",
                "result": {
                    "action": "fetch_user_details",
                    "user_details": result["data"]
                }
            }
        except Exception as e:
            return self._handle_error(f"Error handling fetch user details action: {str(e)}")

    def _handle_wait(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Handle wait actions."""
        try:
            # Validate required fields
            if "duration" not in action:
                return self._handle_error("Missing required field 'duration' for wait action")

            duration = int(action["duration"])
            if duration <= 0:
                return self._handle_error("Duration must be positive")

            # No actual waiting needed here since the frontend will handle it
            return {
                "success": True,
                "type": "action",
                "result": {
                    "action": "wait",
                    "duration": duration
                }
            }
        except Exception as e:
            return self._handle_error(f"Error handling wait action: {str(e)}")

    @staticmethod
    def _handle_complete() -> Dict[str, Any]:
        """Handle task completion."""
        return {
            "success": True,
            "type": "complete",
            "data": "Task completed successfully",
            "message": "Task completed successfully"
        }

    @staticmethod
    def _handle_invalid_action(action: Any) -> Dict[str, Any]:
        """Handle invalid actions."""
        error_msg = f"Invalid action format: {action}. Action must be a dictionary with required fields based on action type:\n" + \
                   "1. Click: action='click', element_description\n" + \
                   "2. Type: action='type', text\n" + \
                   "3. Scroll: action='scroll', direction='up/down', pixels\n" + \
                   "4. Keypress: action='keypress', key='Enter/Tab/Escape'\n" + \
                   "5. Fetch User Details: action='fetch_user_details'\n" + \
                   "6. Complete: action='complete'"
        return {
            "success": False,
            "type": "error",
            "error": error_msg
        }

    @staticmethod
    def _handle_error(error_msg: str) -> Dict[str, Any]:
        """Handle errors."""
        return {
            "success": False,
            "type": "error",
            "error": error_msg
        } 