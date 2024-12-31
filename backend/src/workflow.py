from typing import List, Dict, Any, Union
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
import logging
import json
import os
import re
from dotenv import load_dotenv
from enum import Enum, auto

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('workflow.log')
    ]
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Set higher log levels for noisy libraries
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)

# Load environment variables
load_dotenv()

class ToolName(Enum):
    """Available tools for the agent."""
    EXECUTOR = auto()
    NONE = auto()

    def __str__(self) -> str:
        return self.name.lower()

class Action(BaseModel):
    """Represents an action to be taken."""
    tool: ToolName = Field(..., description="The tool to use")
    input: Dict[str, Any] = Field(..., description="The input parameters for the tool")
    reason: str = Field(..., description="The reason for choosing this action")

class Message(BaseModel):
    """Represents a message in the conversation."""
    role: str = Field(..., description="The role of the message sender")
    content: str = Field(..., description="The content of the message")

class BrowserState(BaseModel):
    """State for browser automation."""
    messages: List[Message] = Field(default_factory=list)
    current_goal: str
    page_state: Dict[str, Any]
    session_id: int
    action_history: List[str] = Field(default_factory=list)
    last_action_result: Union[Dict[str, Any], None] = None

class Tool:
    """Base class for tools."""
    def __init__(self, name: ToolName):
        self.name = name

    def execute(self, input_data: Dict[str, Any], state: BrowserState) -> Dict[str, Any]:
        raise NotImplementedError

class ExecutorTool(Tool):
    """Tool for executing browser actions."""
    def __init__(self):
        super().__init__(ToolName.EXECUTOR)

    def execute(self, input_data: Dict[str, Any], state: BrowserState) -> Dict[str, Any]:
        try:
            action = input_data.get("action", "").lower()
            scroll_match = re.match(r'^scroll\s+(up|down)\s+by\s+(\d+)\s+pixels?$', action)
            if not scroll_match:
                raise ValueError(f"Invalid action format: {action}. Action must be in format: 'scroll [up|down] by [number] pixels'")
            
            direction, pixels = scroll_match.groups()
            action_data = {
                "action": "scroll",
                "direction": direction,
                "pixels": int(pixels)
            }

            return {
                "success": True,
                "result": action_data,
                "message": f"Scrolling {direction} by {pixels} pixels"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

class Agent:
    """ReAct agent for browser automation."""
    def __init__(self):
        self.model = ChatOpenAI(
            model="gpt-4o",
            temperature=0,
            api_key=os.getenv("OPENAI_API_KEY"),
            max_tokens=1000
        )
        self.tools = {
            ToolName.EXECUTOR: ExecutorTool()
        }
        self.max_iterations = 5

    def _get_prompt(self, state: BrowserState) -> str:
        # Create a readable history section
        history_section = ""
        if state.action_history:
            history_section = "Previous actions:\n" + "\n".join(f"- {action}" for action in state.action_history)
            history_section += f"\nTotal actions taken: {len(state.action_history)}"
            if state.last_action_result:
                history_section += "\nLast action result: Success"
        else:
            history_section = "No previous actions taken (0 total actions)"

        return f"""Current goal: {state.current_goal}

You can use these tools:
- executor: Execute scroll actions in format "scroll [up|down] by [number] pixels"

IMPORTANT: Your task is to help users navigate web pages by scrolling. When scrolling to the bottom of a page:

1. Primary Bottom Indicators:
   - Footer elements are the most reliable indicator - if you see a footer, you've reached the bottom
   - Common footer content includes:
     * Copyright notices
     * Social media links
     * Contact information
     * Legal links (Privacy Policy, Terms of Service)
     * Newsletter signup forms

2. Secondary Bottom Indicators:
   - "Load more" or pagination buttons
   - Large empty space after content
   - No more content visible below
   - No scroll change after attempt

3. Scrolling Strategy:
   - Start with large scrolls (800-1000 pixels)
   - When you start seeing any bottom indicators, switch to smaller scrolls (300-500 pixels)
   - If you see a footer, STOP - you've reached the bottom
   - If a scroll doesn't change position, you've reached the bottom

Example Responses:

1. When starting:
{{
    "thought": "No footer visible yet, using a large scroll to move down quickly",
    "action": {{
        "tool": "executor",
        "input": {{
            "action": "scroll down by 1000 pixels"
        }},
        "reason": "Using large scroll to efficiently move towards the bottom"
    }},
    "final_answer": null
}}

2. When seeing the footer:
{{
    "thought": "I can see the page footer with copyright notice and social links - we've reached the bottom",
    "action": {{
        "tool": "none",
        "input": {{}},
        "reason": "Footer is visible, confirming we've reached the bottom of the page"
    }},
    "final_answer": "Successfully scrolled to the bottom of the page"
}}

3. When approaching bottom:
{{
    "thought": "I see some social media icons but not the full footer yet",
    "action": {{
        "tool": "executor",
        "input": {{
            "action": "scroll down by 300 pixels"
        }},
        "reason": "Using smaller scroll as we're likely near the bottom"
    }},
    "final_answer": null
}}

{history_section}

Analyze the screenshot and decide what to do next."""

    def think(self, state: BrowserState) -> Dict[str, Any]:
        """Generate the next action based on current state."""
        # Create messages with both text and image content
        prompt = self._get_prompt(state)
        print(prompt)
        messages = [
            {"role": "system", "content": """You are a web navigation assistant. Your task is to help users navigate web pages by scrolling.
When given a goal and a screenshot, analyze the content and decide how to scroll. Respond with a JSON object (not in a code block)."""},
            {"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": state.page_state["screenshot"]}}
            ]}
        ]
        
        response = self.model.invoke(messages)
        print(response)
        try:
            # Clean up the response content
            content = response.content
            # Remove code block markers if present
            content = re.sub(r'^```json\s*', '', content)
            content = re.sub(r'\s*```$', '', content)
            # Remove any leading/trailing whitespace
            content = content.strip()
            
            parsed_response = json.loads(content)
            return parsed_response
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse response: {response.content}. Error: {str(e)}")
            return {
                "thought": "Error parsing response",
                "action": {"tool": "none", "input": {}, "reason": "Error occurred"},
                "final_answer": "I encountered an error. Please try again."
            }

    def act(self, action: Dict[str, Any], state: BrowserState) -> Dict[str, Any]:
        """Execute the chosen action using the appropriate tool."""
        tool_name = ToolName[action["tool"].upper()]
        if tool_name == ToolName.NONE:
            return {
                "success": True,
                "result": None,
                "message": action.get("reason", "No action needed")
            }

        tool = self.tools.get(tool_name)
        if not tool:
            return {
                "success": False,
                "error": f"Tool {tool_name} not found"
            }

        return tool.execute(action["input"], state)

    def execute(self, state: BrowserState) -> Dict[str, Any]:
        """Main execution loop."""
        iteration = 0
        while iteration < self.max_iterations:
            iteration += 1
            logger.info(f"Starting iteration {iteration}")

            # Think
            response = self.think(state)
            logger.info(f"Thought: {response.get('thought')}")

            # Check for final answer
            if "final_answer" in response and response["final_answer"]:
                return {
                    "type": "complete",
                    "data": response["final_answer"]
                }

            # Act
            action_result = self.act(response["action"], state)
            if not action_result["success"]:
                return {
                    "type": "error",
                    "data": action_result["error"]
                }

            # Update state with human-readable action history
            state.last_action_result = action_result["result"]
            if action_result["result"]:
                action_desc = f"Scrolled {action_result['result']['direction']} by {action_result['result']['pixels']} pixels"
                state.action_history.append(action_desc)
            state.messages.append(Message(
                role="assistant",
                content=action_result["message"]
            ))

            # Return action for execution
            if action_result["result"]:
                # Send both the action message and the action data
                return {
                    "type": "action",
                    "data": action_result["result"],
                    "message": action_result["message"]
                }

        return {
            "type": "error",
            "data": "Reached maximum iterations without achieving goal"
        }

def create_initial_state(session_id: int, goal: str, screenshot: str, html: str) -> BrowserState:
    """Create initial state for the agent."""
    return BrowserState(
        current_goal=goal,
        page_state={
            "screenshot": screenshot,
            "html": html
        },
        session_id=session_id,
        messages=[],
        action_history=[],
        last_action_result=None
    )