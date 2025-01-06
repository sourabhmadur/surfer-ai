"""Browser automation workflow module."""
from typing import List, Dict, Any, Union, Optional
import logging
import json
import os
import re
from enum import Enum, auto
from dotenv import load_dotenv
from prompts import SYSTEM_PROMPT, USER_PROMPT
from llm import LLMProvider
from tools.element_identifier import ElementIdentifier
from tools.screenshot_element_identifier import ScreenshotElementIdentifier
from tools.action_handler import ActionHandler
from models.base import Message, BrowserState

# Configure logging
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class ToolName(Enum):
    """Available tools for the agent."""
    EXECUTOR = auto()
    NONE = auto()

    def __str__(self) -> str:
        return self.name.lower()

class Agent:
    """ReAct agent for browser automation."""
    def __init__(self):
        self.llm = LLMProvider.get_llm()
        self.element_identifier = ElementIdentifier(self.llm)
        self.screenshot_element_identifier = ScreenshotElementIdentifier(self.llm)
        self.action_handler = ActionHandler(self.element_identifier, self.screenshot_element_identifier)
        self.max_iterations = 5

    def think(self, state: BrowserState) -> Dict[str, Any]:
        """Generate next action using LLM."""
        try:
            # Validate state
            if not state or not isinstance(state, BrowserState):
                raise ValueError("Invalid state object")
            
            # Log current state
            logger.debug(f"Thinking about goal: {state.goal}")
            logger.debug(f"HTML length: {len(state.page_state.get('html', ''))}")

            # Initialize conversation if empty
            if not state.llm_conversation:
                # Start with system prompt
                state.llm_conversation.append({
                    "role": "system", 
                    "content": SYSTEM_PROMPT
                })
                # Add initial user message with goal and screenshot
                state.llm_conversation.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": USER_PROMPT.format(goal=state.goal)
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": state.page_state.get("screenshot", "")
                            }
                        }
                    ]
                })
            else:
                # Add current screenshot as latest message with comparison context
                state.llm_conversation.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Compare this screenshot with the previous ones to make your decision. "
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": state.page_state.get("screenshot", "")
                            }
                        }
                    ]
                })

            # Get LLM response
            logger.info("Getting next action from LLM...")
            logger.info(f"Goal: {state.goal}")
            response = self.llm.invoke(state.llm_conversation)
            
            try:
                # Parse the response
                content = response.content
                # Extract JSON part if it exists
                json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
                if json_match:
                    content = json_match.group(1)
                
                parsed_response = json.loads(content)
                logger.info(f"LLM Response: {parsed_response}")

                # Add assistant's response to conversation history
                state.llm_conversation.append({"role": "assistant", "content": content})
                
                # Validate parsed response
                if not isinstance(parsed_response, dict):
                    raise ValueError("LLM response is not a dictionary")
                
                if "action" not in parsed_response:
                    raise ValueError("LLM response missing 'action' field")
                
                return parsed_response
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse LLM response: {str(e)}")
                logger.error(f"Raw response: {response.content}")
                return {
                    "thought": "Error parsing response",
                    "action": "Error: Failed to parse LLM response"
                }
        except Exception as e:
            logger.error(f"Error in think method: {str(e)}", exc_info=True)
            return {
                "thought": "Error occurred",
                "action": f"Error: {str(e)}"
            }

    def execute(self, state: BrowserState) -> Dict[str, Any]:
        """Execute the automation workflow."""
        try:
            for iteration in range(self.max_iterations):
                logger.info(f"Starting iteration {iteration + 1}")
                
                # Get next action
                response = self._get_next_action(state)
                if not response:
                    return self._handle_error("Failed to get next action")

                # Validate response schema
                if not self._validate_llm_response(response):
                    return self._handle_error("Invalid LLM response schema")

                # Handle completion if LLM indicates goal is complete
                if response.get("thought", {}).get("goal_progress", "").lower() == "complete":
                    return self._handle_completion(response.get("thought", {}).get("goal_progress"))

                # Execute action
                result = self._execute_action(response, state)
                if not result["success"]:
                    return result

                # Return action result
                return result

            return self._handle_max_iterations()
        except Exception as e:
            return self._handle_error(f"Error in execute: {str(e)}")

    def _validate_llm_response(self, response: Dict[str, Any]) -> bool:
        """Validate the schema of LLM response."""
        try:
            required_fields = {
                "thought": {
                    "previous_actions": str,
                    "current_state": str,
                    "next_step": str,
                    "goal_progress": str
                },
                "action": {
                    "tool": str,
                    "input": dict,
                    "reason": str
                }
            }

            # Check top-level fields
            if not all(field in response for field in required_fields):
                logger.error(f"Missing top-level fields. Required: {list(required_fields.keys())}, Got: {list(response.keys())}")
                return False

            # Check thought structure
            thought = response.get("thought", {})
            thought_fields = required_fields["thought"]
            if not all(field in thought and isinstance(thought[field], field_type) 
                      for field, field_type in thought_fields.items()):
                logger.error(f"Invalid thought structure. Required: {thought_fields}, Got: {thought}")
                return False

            # Check action structure
            action = response.get("action", {})
            action_fields = required_fields["action"]
            if not all(field in action and isinstance(action[field], field_type) 
                      for field, field_type in action_fields.items()):
                logger.error(f"Invalid action structure. Required: {action_fields}, Got: {action}")
                return False

            return True
        except Exception as e:
            logger.error(f"Error validating LLM response: {str(e)}")
            return False

    def _get_next_action(self, state: BrowserState) -> Optional[Dict[str, Any]]:
        """Get next action from LLM."""
        try:
            response = self.think(state)
            logger.info(f"Thought: {response.get('thought')}")
            return response
        except Exception as e:
            logger.error(f"Error getting next action: {str(e)}")
            return None

    def _execute_action(self, response: Dict[str, Any], state: BrowserState) -> Dict[str, Any]:
        """Execute the chosen action."""
        try:
            # Handle error responses from think method
            if isinstance(response.get("action"), str) and response["action"].startswith("Error:"):
                return self._handle_error(response["action"])

            if "action" not in response:
                return self._handle_error("No action provided in response")

            action = response["action"]
            logger.info(f"Executing action: {action}")

            # Handle direct action string
            if isinstance(action, str):
                return self.action_handler.handle_action(action, state)
            
            # Handle action object format
            if isinstance(action, dict):
                if "input" in action and "action" in action["input"]:
                    return self.action_handler.handle_action(action["input"]["action"], state)
                elif "name" in action and "input" in action:
                    return self.action_handler.handle_action(action["input"], state)

            return self._handle_error(f"Invalid action format: {action}")
        except Exception as e:
            logger.error(f"Error executing action: {str(e)}")
            return self._handle_error(f"Error executing action: {str(e)}")

    @staticmethod
    def _handle_completion(final_answer: str) -> Dict[str, Any]:
        """Handle task completion."""
        return {
            "success": True,
            "type": "complete",
            "data": final_answer
        }

    @staticmethod
    def _handle_max_iterations() -> Dict[str, Any]:
        """Handle reaching maximum iterations."""
        return {
            "success": False,
            "type": "error",
            "error": "Reached maximum iterations without achieving goal"
        }

    @staticmethod
    def _handle_error(error_msg: str) -> Dict[str, Any]:
        """Handle errors."""
        return {
            "success": False,
            "type": "error",
            "error": error_msg
        }

def create_initial_state(session_id: int, goal: str, screenshot: str, html: str) -> BrowserState:
    """Create initial state for the agent."""
    try:
        # Validate inputs
        if not isinstance(session_id, int):
            raise ValueError("session_id must be an integer")
        if not goal or not isinstance(goal, str):
            raise ValueError("goal must be a non-empty string")
        if not isinstance(html, str):
            raise ValueError("html must be a string")
        if not isinstance(screenshot, str):
            raise ValueError("screenshot must be a string")
        
        logger.info(f"Creating initial state with goal: {goal}")
        
        # Create state with validated inputs
        state = BrowserState(
            goal=goal,
            page_state={
                "screenshot": screenshot,
                "html": html
            },
            session_id=session_id,
            messages=[],
            last_action_result=None,
            llm_conversation=[]
        )
        
        # Verify state was created correctly
        if not state.goal:
            raise ValueError("State created with empty goal")
        if not state.page_state:
            raise ValueError("State created with empty page_state")
            
        logger.info("State created successfully")
        return state
    except Exception as e:
        logger.error(f"Error creating state: {str(e)}", exc_info=True)
        raise ValueError(f"Failed to create state: {str(e)}")