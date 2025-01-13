"""Handles execution of browser actions."""
import logging
import re
from typing import Dict, Any
from models.base import BrowserState
from tools.element_identifier import ElementIdentifier
from tools.user_details_fetcher import UserDetailsFetcher

logger = logging.getLogger(__name__)

class ActionHandler:
    """Handles execution of browser actions."""
    def __init__(self, element_identifier: ElementIdentifier):
        self.element_identifier = element_identifier
        self.user_details_fetcher = UserDetailsFetcher()

    def handle_action(self, action: str, state: BrowserState) -> Dict[str, Any]:
        """Handle different types of actions."""
        try:
            # Parse action JSON if it's a string
            if isinstance(action, str):
                try:
                    import json
                    action_data = json.loads(action)
                    if isinstance(action_data, dict) and "action" in action_data:
                        action = action_data
                except json.JSONDecodeError:
                    pass

            # Handle action object format
            if isinstance(action, dict) and "action" in action:
                action_type = action["action"].lower()
                logger.info(f"=== Executing Action === {action_type}")

                if action_type == "complete":
                    return self._handle_complete(action)

                handlers = {
                    "type": self._handle_type,
                    "click": self._handle_click,
                    "scroll": self._handle_scroll,
                    "keypress": self._handle_keypress,
                    "fetch_user_details": self._handle_fetch_user_details
                }

                if action_type in handlers:
                    return handlers[action_type](action, state)

            return self._handle_invalid_action(action)
        except Exception as e:
            return self._handle_error(str(e))

    def _handle_type(self, action: Dict[str, Any], state: BrowserState) -> Dict[str, Any]:
        """Handle type actions."""
        try:
            # Validate required fields
            if "text" not in action:
                return self._handle_error("Missing required field 'text' for type action")

            text_to_type = action["text"]

            # Direct typing without element identification
            return {
                "success": True,
                "type": "action",
                "result": {
                    "action": "type",
                    "text": text_to_type
                }
            }
        except Exception as e:
            return self._handle_error(f"Error handling type action: {str(e)}")

    def _handle_click(self, action: Dict[str, Any], state: BrowserState) -> Dict[str, Any]:
        """Handle click actions."""
        try:
            # Validate required fields
            if "element_description" not in action:
                return self._handle_error("Missing required field 'element_description' for click action")

            element_desc = action["element_description"]
            
            # Get screenshot from state
            screenshot = state.page_state.get("screenshot")
            
            # Identify the element with screenshot
            element_result = self.element_identifier.identify_element(
                element_desc, 
                state.page_state["html"],
                screenshot
            )
            
            if not element_result["success"]:
                return self._handle_error(element_result["error"])
            
            element_data = element_result["element_data"]
            
            return {
                "success": True,
                "type": "action",
                "result": {
                    "action": "click",
                    "element_data": {
                        "selector": element_data["selector"],
                        "element_type": element_data["element_type"],
                        "text_content": element_data["text_content"]
                    }
                }
            }
        except Exception as e:
            return self._handle_error(f"Error handling click action: {str(e)}")

    def _handle_scroll(self, action: Dict[str, Any], state: BrowserState) -> Dict[str, Any]:
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

            return {
                "success": True,
                "type": "action",
                "result": {
                    "action": "scroll",
                    "direction": direction,
                    "pixels": pixels
                }
            }
        except Exception as e:
            return self._handle_error(f"Error handling scroll action: {str(e)}")

    def _handle_keypress(self, action: Dict[str, Any], state: BrowserState) -> Dict[str, Any]:
        """Handle keypress actions."""
        try:
            # Validate required fields
            if "key" not in action:
                return self._handle_error("Missing required field 'key' for keypress action")

            key = action["key"].lower()
            valid_keys = ["enter", "tab", "escape"]
            
            if key not in valid_keys:
                return self._handle_error(f"Invalid key: {key}. Valid keys are: {', '.join(valid_keys)}")

            return {
                "success": True,
                "type": "action",
                "result": {
                    "action": "keypress",
                    "key": key
                }
            }
        except Exception as e:
            return self._handle_error(f"Error handling keypress action: {str(e)}")

    def _handle_fetch_user_details(self, action: Dict[str, Any], state: BrowserState) -> Dict[str, Any]:
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

    @staticmethod
    def _handle_complete(action: Dict[str, Any]) -> Dict[str, Any]:
        """Handle task completion."""
        return {
            "success": True,
            "type": "complete",
            "data": "Task completed successfully",
            "message": action.get("reason", "Task completed successfully")
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