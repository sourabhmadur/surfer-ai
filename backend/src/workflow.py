"""Browser automation workflow module."""
from typing import List, Dict, Any, Union, Optional
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
import logging
import json
import os
import re
from enum import Enum, auto
from dotenv import load_dotenv
from prompts import SYSTEM_PROMPT, USER_PROMPT
from llm import LLMProvider

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

class Message(BaseModel):
    """Represents a message in the conversation."""
    role: str
    content: str

class BrowserState(BaseModel):
    """State for browser automation."""
    messages: List[Message] = Field(default_factory=list)
    goal: str = Field(..., min_length=1)
    page_state: Dict[str, Any] = Field(...)
    session_id: int = Field(...)
    last_action_result: Optional[Dict[str, Any]] = None
    llm_conversation: List[Dict[str, Any]] = Field(default_factory=list)

class ElementIdentifier:
    """Handles element identification using LLM."""
    def __init__(self, model):
        self.model = model

    def identify_element(self, element_desc: str, html: str) -> Dict[str, Any]:
        """Identify DOM element based on description."""
        logger.info(f"=== Identifying Element === Description: {element_desc}")
        
        try:
            # Get LLM response
            response = self._get_llm_response(element_desc, html)
            element_data = self._parse_llm_response(response)
            
            # Validate and log results
            self._validate_and_log_results(element_data, element_desc)
            
            return {
                "success": True,
                "element_data": element_data
            }
        except Exception as e:
            logger.error(f"Failed to identify element: {str(e)}")
            return {
                "success": False,
                "error": f"Failed to identify element: {str(e)}"
            }

    def _get_llm_response(self, element_desc: str, html: str) -> str:
        """Get response from LLM."""
        prompt = self._build_prompt(element_desc, html)
        messages = self._build_messages(prompt)
        
        logger.info("Sending request to LLM...")
        response = self.model.invoke(messages)
        logger.info(f"Raw LLM response: {response.content}")
        return response.content

    def _parse_llm_response(self, content: str) -> Dict[str, Any]:
        """Parse LLM response into structured data."""
        cleaned_content = re.sub(r'^```json\s*|\s*```$', '', content.strip())
        return json.loads(cleaned_content)

    def _validate_and_log_results(self, element_data: Dict[str, Any], element_desc: str):
        """Validate and log element identification results."""
        logger.info("=== Element Identified ===")
        logger.info(f"Selector: {element_data.get('selector')}")
        logger.info(f"Element Type: {element_data.get('element_type')}")
        logger.info(f"Text Content: {element_data.get('text_content')}")
        logger.info(f"Confidence: {element_data.get('confidence')}")

        if element_data.get('confidence', 0) < 0.7:
            logger.warning(f"Low confidence ({element_data.get('confidence')}) for element: {element_desc}")
        
        if not element_data.get('selector'):
            logger.error("No selector returned by LLM")
        elif 'http' in element_data['selector'].lower():
            logger.warning("Selector contains URL - this might be fragile")

    @staticmethod
    def _build_prompt(element_desc: str, html: str) -> str:
        """Build prompt for element identification."""
        return f"""Given the HTML content and element description below, identify the most appropriate DOM element.

Element Description: {element_desc}

HTML Content:
{html}

You MUST respond with a JSON object in this EXACT format:
{{
    "selector": "CSS selector to uniquely identify the element",
    "element_type": "Type of element (e.g., button, link, input)",
    "text_content": "Visible text content of the element",
    "confidence": "Number between 0 and 1 indicating confidence in the match"
}}

Requirements for selector generation:
1. PREFER these selector strategies in order:
   - Link text using attribute selector: a[href][title='exact text']
   - Link text using partial match: a[href*='relevant-text']
   - Unique attributes: [data-testid='x'], [aria-label='x']
   - Unique classes: .specific-class
   - Combinations of simple attributes
2. AVOID these invalid or fragile selectors:
   - jQuery selectors like :contains() (NOT valid CSS)
   - Complex child selectors with multiple levels
   - Numeric or generated IDs (they often change)
   - Position-based selectors like nth-child
   - Full XPaths
3. For links/buttons with text:
   - Use href/title/aria-label attributes
   - Or use parent class + element type
4. Keep selectors simple and valid CSS
5. Test that selector works in the provided HTML
6. Never use jQuery-specific selectors

Example Responses:
For a link with text "Sign up":
{{
    "selector": "a[title='Sign up']",
    "element_type": "link",
    "text_content": "Sign up",
    "confidence": 0.95
}}

For a link in a specific section:
{{
    "selector": ".article-section a[href*='minecraft']",
    "element_type": "link",
    "text_content": "Minecraft Article",
    "confidence": 0.95
}}

For a button:
{{
    "selector": "[data-testid='submit-button']",
    "element_type": "button",
    "text_content": "Submit Form",
    "confidence": 0.95
}}

Analyze the HTML and provide the element details in the specified JSON format."""

    @staticmethod
    def _build_messages(prompt: str) -> List[Dict[str, str]]:
        """Build messages for LLM."""
        return [
            {
                "role": "system", 
                "content": """You are an expert at analyzing HTML and identifying DOM elements. 
                You ALWAYS respond with valid JSON in the exact format specified in the prompt.
                You NEVER include explanations or additional text outside the JSON structure."""
            },
            {"role": "user", "content": prompt}
        ]

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
    def _validate_action(action: Dict[str, Any]) -> bool:
        """Validate action format."""
        if isinstance(action, str):
            return True
        if isinstance(action, dict):
            # Check for input.action format
            if "input" in action and isinstance(action["input"], dict) and "action" in action["input"]:
                return True
            # Check for name/input format
            if "name" in action and "input" in action:
                return True
        return False

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