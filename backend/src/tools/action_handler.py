"""Handles execution of browser actions."""
import logging
import re
from typing import Dict, Any
from models.base import BrowserState
from tools.element_identifier import ElementIdentifier

logger = logging.getLogger(__name__)

class ActionHandler:
    """Handles execution of browser actions."""
    def __init__(self, element_identifier: ElementIdentifier):
        self.element_identifier = element_identifier

    def handle_action(self, action: str, state: BrowserState) -> Dict[str, Any]:
        """Handle different types of actions."""
        try:
            action = action.lower()
            logger.info(f"=== Executing Action === {action}")

            if action == "complete":
                return self._handle_complete(action)
            
            handlers = {
                "type": self._handle_type,
                "click": self._handle_click,
                "scroll": self._handle_scroll
            }

            for action_type, handler in handlers.items():
                if action.startswith(action_type):
                    return handler(action, state)

            return self._handle_invalid_action(action)
        except Exception as e:
            return self._handle_error(str(e))

    def _handle_type(self, action: str, state: BrowserState) -> Dict[str, Any]:
        """Handle type actions."""
        try:
            # Extract text and target element description
            match = re.match(r'type\s+([^"]+?)(?:\s+into\s+(.+))?$', action)
            if not match:
                return self._handle_invalid_action(action)

            # Clean the text by removing quotes
            text_to_type = match.group(1).strip("'\"")
            element_desc = match.group(2)

            # If element description is provided, identify the element
            if element_desc:
                element_result = self.element_identifier.identify_element(element_desc, state.page_state["html"])
                if not element_result["success"]:
                    return self._handle_error(element_result["error"])
                
                element_data = element_result["element_data"]
                return {
                    "success": True,
                    "type": "action",
                    "result": {
                        "action": "type",
                        "text": text_to_type,
                        "element_data": {
                            "selector": element_data["selector"],
                            "element_type": element_data["element_type"],
                            "text_content": element_data["text_content"]
                        }
                    }
                }
            else:
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

    def _handle_click(self, action: str, state: BrowserState) -> Dict[str, Any]:
        """Handle click actions."""
        try:
            # Extract element description
            match = re.match(r'click\s+(?:on\s+)?(.+)$', action)
            if not match:
                return self._handle_invalid_action(action)

            element_desc = match.group(1)
            
            # Identify the element
            element_result = self.element_identifier.identify_element(element_desc, state.page_state["html"])
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

    def _handle_scroll(self, action: str, state: BrowserState) -> Dict[str, Any]:
        """Handle scroll actions."""
        try:
            # Extract direction and pixels
            match = re.match(r'scroll\s+(up|down)\s+by\s+(\d+)\s+pixels?', action)
            if not match:
                return self._handle_invalid_action(action)

            direction = match.group(1)
            pixels = int(match.group(2))

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
    def _handle_invalid_action(action: str) -> Dict[str, Any]:
        """Handle invalid actions."""
        error_msg = f"Invalid action format: {action}. Supported formats:\n" + \
                   "1. 'click on [element description]'\n" + \
                   "2. 'scroll [up|down] by [number] pixels'\n" + \
                   "3. 'type [text]' or 'type [text] into [element description]'\n" + \
                   "4. 'complete' (when task is finished)"
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