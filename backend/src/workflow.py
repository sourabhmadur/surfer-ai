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
from tools.action_handler import ActionHandler
from models.base import Message, BrowserState, Observation
from src.utils.logging import truncate_data

# Get logger with the full module path
logger = logging.getLogger("src.workflow")

# Load environment variables
load_dotenv()

class ToolName(Enum):
    """Available tools for the agent."""
    EXECUTOR = auto()
    NONE = auto()

    def __str__(self) -> str:
        return self.name.lower()

class Agent:
    """Browser automation agent."""
    
    def __init__(self):
        """Initialize the agent."""
        self.max_iterations = 10
        self.llm = LLMProvider.get_llm()
        self.action_handler = ActionHandler(llm=self.llm)

    def think(self, state: BrowserState) -> Dict[str, Any]:
        """Generate next action using LLM."""
        try:
            # Validate state
            if not state or not isinstance(state, BrowserState):
                raise ValueError("Invalid state object")
            
            # Log current state
            logger.info(f"Thinking about goal: {state.goal}")
            logger.info(f"Current observations count: {len(state.observations)}")
            if state.observations:
                logger.info("=== Current Observation ===")
                logger.info(f"Screenshot size: {len(state.observations[-1].screenshot)} bytes")
                logger.info(f"HTML size: {len(state.observations[-1].html)} bytes")

            # Build conversation for LLM
            logger.info("=== Building LLM Conversation ===")
            conversation = []
            
            # Add system prompt with goal
            conversation.append({
                "role": "system", 
                "content": f"{SYSTEM_PROMPT}\n\nCurrent Goal: {state.goal}"
            })
            logger.info("Added system prompt")

            # Add past actions summary if any
            past_actions_text = ""
            if state.past_actions:
                logger.info(f"Adding {len(state.past_actions)} past actions")
                actions_list = []
                for action_data in state.past_actions:
                    try:
                        # Use the description field that was added by add_action
                        if "description" in action_data:
                            actions_list.append(action_data["description"])
                        else:
                            # Fallback to basic action type if no description
                            actions_list.append(f"Action: {action_data.get('action', 'unknown')}")
                    except Exception as e:
                        logger.error(f"Error formatting action: {str(e)}")
                        continue
                
                if actions_list:
                    past_actions_text = "Past actions:\n" + "\n".join(f"- {action}" for action in actions_list)
                    logger.info(f"Past actions:\n{past_actions_text}")
                else:
                    logger.info("No past actions to format")
            else:
                logger.info("No past actions")

            logger.info(f"Observations length: {len(state.observations)}")
            
            # Add current observation with context
            if state.observations:
                # Add previous screenshots if available
                if len(state.observations) > 1:
                    previous_screenshots = []
                    for obs in reversed(state.observations[:-1]):
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
            logger.info("=== Calling LLM ===")
            logger.info(f"Conversation length: {len(conversation)} messages")
            try:
                response = self.llm.invoke(conversation)
                logger.info("Got response from LLM")
                
                # Log truncated response
                content = response.content
                truncated_content = truncate_data({"content": content})["content"]
                logger.info("=== Raw LLM Response ===")
                logger.info(f"{truncated_content}")
                
                try:
                    # Parse the response
                    logger.info("=== Processing LLM Response ===")
                    
                    # Extract JSON part if it exists
                    json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
                    if json_match:
                        content = json_match.group(1)
                        logger.info("Found JSON block")
                        logger.info("=== Extracted JSON Content ===")
                        logger.info(truncate_data({"content": content})["content"])
                    else:
                        logger.error("No JSON block found in LLM response")
                        logger.info("Attempting to parse entire response as JSON")

                    # Clean up common JSON formatting issues
                    content = re.sub(r',(\s*[}\]])', r'\1', content)  # Remove trailing commas
                    content = re.sub(r',\s*\n\s*([}\]])', r'\1', content)  # Remove trailing commas with newlines
                    content = re.sub(r'\n\s*([}\]])', r'\1', content)  # Remove extra newlines
                    content = content.strip()
                    
                    logger.info("=== Cleaned Content ===")
                    logger.info(content)
                    
                    try:
                        parsed_response = json.loads(content)
                        logger.info("=== Successfully Parsed JSON ===")
                        logger.info(json.dumps(parsed_response, indent=2))

                        # Validate response structure
                        if not isinstance(parsed_response, dict):
                            raise ValueError(f"LLM response is not a dictionary. Got: {type(parsed_response)}")
                        
                        required_fields = ["thought", "action"]
                        missing_fields = [field for field in required_fields if field not in parsed_response]
                        if missing_fields:
                            raise ValueError(f"LLM response missing required fields: {missing_fields}")
                        
                        # Validate thought structure
                        thought = parsed_response["thought"]
                        if not isinstance(thought, dict):
                            raise ValueError(f"'thought' must be a dictionary. Got: {type(thought)}")
                        
                        required_thought_fields = ["goal", "current_state", "next_step"]
                        missing_thought_fields = [field for field in required_thought_fields if field not in thought]
                        if missing_thought_fields:
                            raise ValueError(f"'thought' missing required fields: {missing_thought_fields}")
                        
                        # Validate action structure
                        action = parsed_response["action"]
                        if not isinstance(action, dict):
                            raise ValueError(f"'action' must be a dictionary. Got: {type(action)}")
                        
                        if "tool" not in action:
                            raise ValueError("'action' missing 'tool' field")
                        
                        # Parse and validate the action structure
                        if parsed_response["action"]["tool"] == "executor":
                            action_input = parsed_response["action"]["input"]
                            
                            # Add element identification for click actions
                            if action_input.get("action") == "click":
                                if "element_description" in action_input:
                                    # Get element data using element identifier
                                    element_desc = action_input["element_description"]
                                    html = state.observations[-1].html if state.observations else ""
                                    screenshot = state.observations[-1].screenshot if state.observations else ""
                                    
                                    element_result = self.action_handler.element_identifier.identify_element(
                                        element_desc=element_desc,
                                        html=html,
                                        screenshot=screenshot
                                    )
                                    
                                    if not element_result["success"]:
                                        logger.error(f"Failed to identify element: {element_result.get('error')}")
                                        return {
                                            "success": False,
                                            "error": f"Failed to identify element: {element_result.get('error')}"
                                        }
                                        
                                    # Update action with element data
                                    action_input["element_data"] = element_result["element_data"]
                                    parsed_response["action"]["input"] = action_input
                            elif action_input.get("action") == "keypress":
                                # Validate keypress action
                                key = action_input.get("key", "").lower()
                                if key not in ["enter", "tab", "escape"]:
                                    logger.error(f"Invalid key: {key}")
                                    return {
                                        "success": False,
                                        "error": f"Invalid key: {key}. Valid keys are: enter, tab, escape"
                                    }

                        return parsed_response

                    except json.JSONDecodeError as e:
                        logger.error(f"JSON Parse Error: {str(e)}")
                        logger.error(f"Error location: line {e.lineno}, column {e.colno}")
                        logger.error(f"Error context: {e.doc[max(0, e.pos-50):e.pos+50]}")
                        return {
                            "thought": {
                                "goal": state.goal,
                                "previous_actions": [],
                                "current_state": "Error parsing LLM response",
                                "next_step": "Failed to parse response, stopping execution",
                                "tentative_plan": ["stop:error"],
                                "goal_progress": "error"
                            },
                            "action": {
                                "tool": "executor",
                                "input": {
                                    "action": "complete"  # Stop execution instead of waiting
                                },
                                "reason": "Failed to parse LLM response"
                            }
                        }

                except Exception as e:
                    logger.error(f"Error processing LLM response: {str(e)}")
                    return {
                        "thought": {
                            "goal": state.goal,
                            "previous_actions": [],
                            "current_state": f"Error: {str(e)}",
                            "next_step": "Failed to process response, stopping execution",
                            "tentative_plan": ["stop:error"],
                            "goal_progress": "error"
                        },
                        "action": {
                            "tool": "executor",
                            "input": {
                                "action": "complete"  # Stop execution instead of waiting
                            },
                            "reason": "Failed to process LLM response"
                        }
                    }

            except Exception as e:
                logger.error(f"Error calling LLM: {str(e)}")
                raise

        except Exception as e:
            # Clean up error message if it contains base64 data
            error_msg = str(e)
            if "data:image/" in error_msg or ";base64," in error_msg:
                error_msg = "Error processing image data"
            
            logger.error(f"Error in think method: {error_msg}")
            return {
                "thought": {
                    "goal": state.goal if state else "unknown",
                    "previous_actions": [],
                    "current_state": f"Error: {error_msg}",
                    "next_step": "Failed to execute, stopping",
                    "tentative_plan": ["stop:error"],
                    "goal_progress": "error"
                },
                "action": {
                    "tool": "executor",
                    "input": {
                        "action": "complete"  # Stop execution instead of waiting
                    },
                    "reason": "Error in think method"
                }
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
                action_input = response.get("action", {}).get("input", {})
                if not action_input:
                    return self._handle_error("Missing action input")

                # Use state's add_action method to properly track the action
                state.add_action(action_input)

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
        """Execute the next action."""
        try:
            # Add debug logging
            logger.info("=== Executing Action ===")
            logger.info(f"Current past_actions count: {len(state.past_actions) if state.past_actions else 0}")
            
            # Get action details
            action = response.get("action", {})
            tool_name = action.get("tool", "").lower()
            action_input = action.get("input", {})
            
            # Execute action using appropriate tool
            if tool_name == str(ToolName.EXECUTOR):
                # Execute action
                result = self.action_handler.handle_action(action_input)
                
                # Add more debug logging
                logger.info(f"Past actions after execution: {len(state.past_actions)}")
                if state.past_actions:
                    logger.info(f"Last action added: {state.past_actions[-1]}")
                
                return result
            else:
                return self._handle_error(f"Unknown tool: {tool_name}")
            
        except Exception as e:
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

def create_initial_state(goal: str, screenshot: str, html: str, session_id: int) -> BrowserState:
    """Create initial browser state."""
    logger.info(f"Creating initial state with goal: {goal}")
    
    # Create initial observation
    observation = Observation(
        screenshot=screenshot,
        html=html,
        session_id=session_id
    )
    logger.info("Created initial observation")
    
    # Create initial state
    state = BrowserState(
        goal=goal,
        observations=[observation],
        past_actions=[],  # Explicitly initialize empty list
        session_id=session_id  # Add session_id here
    )
    logger.info(f"Initial state created with {len(state.past_actions)} past actions")
    
    return state