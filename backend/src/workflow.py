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
from tools.action_handler import ActionHandler
from models.base import Message, BrowserState, Observation

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
        self.action_handler = ActionHandler(self.element_identifier)
        self.max_iterations = 5

    def think(self, state: BrowserState) -> Dict[str, Any]:
        """Generate next action using LLM."""
        try:
            # Validate state
            if not state or not isinstance(state, BrowserState):
                raise ValueError("Invalid state object")
            
            # Log current state
            logger.debug(f"Thinking about goal: {state.goal}")
            logger.info(f"Current observations count: {len(state.observations)}")
            if state.observations:
                logger.debug(f"HTML length: {len(state.observations[-1].html)}")
                logger.info(f"Timestamps of observations: {[obs.timestamp for obs in state.observations]}")

            # Build conversation for LLM
            conversation = []
            
            # Add system prompt with goal
            conversation.append({
                "role": "system", 
                "content": f"{SYSTEM_PROMPT}\n\nCurrent Goal: {state.goal}"
            })

            # Add past actions summary if any
            past_actions_text = ""
            if state.past_actions:
                actions_list = []
                for action_data in state.past_actions:
                    if isinstance(action_data, dict) and "input" in action_data:
                        action_input = action_data["input"]
                        action_type = action_input.get("action", "unknown")
                        
                        # Build description based on action type
                        if action_type == "click":
                            desc = f"Clicked on: {action_input.get('element_description', 'unknown element')}"
                        elif action_type == "type":
                            desc = f"Typed text: {action_input.get('text', '')}"
                        elif action_type == "scroll":
                            desc = f"Scrolled {action_input.get('direction', 'unknown')} by {action_input.get('pixels', '0')} pixels"
                        elif action_type == "keypress":
                            desc = f"Pressed key: {action_input.get('key', 'unknown')}"
                        elif action_type == "fetch_user_details":
                            desc = "Fetched user details"
                        elif action_type == "complete":
                            desc = "Completed task"
                        else:
                            desc = f"Unknown action: {action_type}"
                        
                        actions_list.append(desc)
                
                if actions_list:
                    past_actions_text = "Past actions:\n" + "\n".join(f"- {action}" for action in actions_list)
            logger.info(f"Past actions: {past_actions_text}")
            logger.info(f"Observations length: {len(state.observations)}")
            
            # Add current observation with context
            if state.observations:
                # Add previous screenshots if available
                if len(state.observations) > 1:
                    previous_screenshots = []
                    for obs in reversed(state.observations[:-1]):  # Skip the latest one as it's already added
                        previous_screenshots.append({
                            "type": "image_url",
                            "image_url": {
                                "url": obs.screenshot
                            }
                        })
                    
                    if previous_screenshots:
                        conversation.append({
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": "Here are the previous screenshots for comparison:"
                                },
                                *previous_screenshots
                            ]
                        })

                # Add current screenshot with context
                conversation.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"{past_actions_text}\n\nAnalyze the current screenshot and determine the next action."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": state.observations[-1].screenshot
                            }
                        }
                    ]
                })

            # Get LLM response
            logger.info("Getting next action from LLM...")
            logger.info(f"Goal: {state.goal}")
            response = self.llm.invoke(conversation)
            
            try:
                # Parse the response
                content = response.content
                # Extract JSON part if it exists
                json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
                if json_match:
                    content = json_match.group(1)
                
                # Clean up common JSON formatting issues
                content = re.sub(r',(\s*[}\]])', r'\1', content)  # Remove trailing commas before closing brackets
                content = re.sub(r',\s*\n\s*([}\]])', r'\1', content)  # Remove trailing commas with newlines
                content = re.sub(r'\n\s*([}\]])', r'\1', content)  # Remove extra newlines before closing brackets
                content = content.strip()  # Remove extra whitespace
                
                try:
                    parsed_response = json.loads(content)
                    logger.info(f"LLM Response: {json.dumps(parsed_response, indent=2)}")
                except json.JSONDecodeError:
                    # If still fails, try more aggressive cleanup
                    content = re.sub(r',(\s*[}\]])', r'\1', content)  # More aggressive trailing comma removal
                    content = re.sub(r'[\t\n\r]', '', content)  # Remove all whitespace
                    content = re.sub(r',}', '}', content)
                    parsed_response = json.loads(content)
                    logger.info(f"Could not parse LLM Response: {json.dumps(parsed_response, indent=2)}")

                # Store the action in past_actions if it's valid
                if isinstance(parsed_response, dict) and "action" in parsed_response:
                    action_to_store = parsed_response["action"]
                    if isinstance(action_to_store, dict) and "tool" in action_to_store:
                        state.past_actions.append(action_to_store)
                
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
                "thought": f"Error: {str(e)}",
                "action": "Error: Failed to generate next action"
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
            # Check top-level fields
            if not isinstance(response, dict):
                logger.error("Response is not a dictionary")
                return False

            if "thought" not in response or "action" not in response:
                logger.error(f"Missing required top-level fields. Got: {list(response.keys())}")
                return False

            # Check thought structure - validate required fields
            thought = response.get("thought", {})
            required_thought_fields = {
                "goal",
                "previous_actions", 
                "current_state", 
                "next_step", 
                "tentative_plan",
                "goal_progress"
            }
            
            if not all(field in thought for field in required_thought_fields):
                logger.error(f"Missing thought fields. Required: {required_thought_fields}, Got: {list(thought.keys())}")
                return False

            # Check action structure - be more lenient
            action = response.get("action", {})
            if not isinstance(action, dict):
                logger.error("Action is not a dictionary")
                return False

            # For executor tool, validate input structure
            if action.get("tool") == "executor":
                if "input" not in action or not isinstance(action["input"], dict):
                    logger.error("Missing or invalid input field for executor tool")
                    return False
                
                if "action" not in action["input"]:
                    logger.error("Missing action field in executor input")
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
                result = self.action_handler.handle_action(action, state)
            # Handle action object format
            elif isinstance(action, dict):
                # Handle nested action format from LLM
                if "input" in action and isinstance(action["input"], dict):
                    result = self.action_handler.handle_action(action["input"], state)
                # Handle direct action format
                elif "action" in action:
                    result = self.action_handler.handle_action(action, state)
                else:
                    return self._handle_error(f"Invalid action format: {action}")
            else:
                return self._handle_error(f"Invalid action format: {action}")

            # Store the action result in state
            if result["success"]:
                state.last_action_result = result

            return result
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
        
        # Create initial observation
        initial_observation = Observation(
            screenshot=screenshot,
            html=html
        )
        logger.info("Created initial observation")
        
        # Create state with validated inputs
        state = BrowserState(
            goal=goal,
            session_id=session_id,
            observations=[initial_observation]  # Initialize with first observation
        )
        logger.info(f"Initial state created with {len(state.observations)} observations")
        
        # Verify state was created correctly
        if not state.goal:
            raise ValueError("State created with empty goal")
        if not state.observations:
            raise ValueError("State created with empty observations")
            
        logger.info(f"State created successfully. Observations count: {len(state.observations)}")
        return state
    except Exception as e:
        logger.error(f"Error creating state: {str(e)}", exc_info=True)
        raise ValueError(f"Failed to create state: {str(e)}")