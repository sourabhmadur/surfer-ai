import base64
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import requests
import json
from typing import Optional, Dict, Any
import logging
from src.utils.logging import truncate_data

# Get logger with the full module path
logger = logging.getLogger("src.tools.selenium_agent")

class SeleniumAgent:
    """Selenium-based web automation agent."""
    
    def __init__(self, url: str = "http://localhost:8000"):
        self.base_url = url
        self.driver: Optional[webdriver.Chrome] = None
        
    def setup(self):
        """Setup the browser environment."""
        self.driver = webdriver.Chrome()
        
    def teardown(self):
        """Cleanup the browser environment."""
        if self.driver:
            self.driver.quit()
            
    def get_page_state(self) -> Dict[str, str]:
        """Get the current page state including screenshot and HTML."""
        try:
            # Take screenshot
            screenshot = self.driver.get_screenshot_as_base64()
            # Format screenshot for LLM
            screenshot_data = f'data:image/png;base64,{screenshot}'
            
            # Get HTML
            html = self.driver.page_source
            
            return {
                "screenshot": screenshot_data,
                "html": html
            }
        except Exception as e:
            logger.error(f"Error getting page state: {str(e)}")
            raise
    
    def execute_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Execute browser action using Selenium."""
        if not self.driver:
            raise RuntimeError("WebDriver not initialized")
            
        try:
            # Log truncated action data
            log_action = action.copy()
            if 'screenshot' in log_action:
                log_action['screenshot'] = '[TRUNCATED]'
            
            if action["action"] == "click":
                element = self.driver.find_element(By.CSS_SELECTOR, action["element_data"]["selector"])
                element.click()
                logger.info(f"Clicked element with selector: {action['element_data']['selector']}")
            elif action["action"] == "type":
                # For type actions, use the active element or find the input element
                try:
                    # First try using active element
                    active_element = self.driver.switch_to.active_element
                    active_element.send_keys(action["text"])
                    logger.info(f"Typed text using active element: {action['text']}")
                except Exception as e:
                    logger.warning(f"Failed to type using active element: {str(e)}")
                    # Fallback: try to find the last clicked input element
                    input_element = self.driver.find_element(By.CSS_SELECTOR, "input:focus")
                    input_element.send_keys(action["text"])
                    logger.info(f"Typed text using focused input: {action['text']}")
            elif action["action"] == "scroll":
                if action["direction"] == "down":
                    self.driver.execute_script(f"window.scrollBy(0, {action['pixels']});")
                else:
                    self.driver.execute_script(f"window.scrollBy(0, -{action['pixels']});")
                logger.info(f"Scrolled {action['direction']} by {action['pixels']} pixels")
            elif action["action"] == "keypress":
                from selenium.webdriver.common.keys import Keys
                key_map = {
                    "enter": Keys.ENTER,
                    "tab": Keys.TAB,
                    "escape": Keys.ESCAPE
                }
                active_element = self.driver.switch_to.active_element
                active_element.send_keys(key_map[action["key"].lower()])
                logger.info(f"Pressed key: {action['key']}")
            elif action["action"] == "wait":
                time.sleep(action["duration"])
                logger.info(f"Waited for {action['duration']} seconds")
                
            # Get updated page state after action
            page_state = self.get_page_state()
            logger.info("Successfully captured new page state")
            
            # Return success response with updated page state
            return {
                "success": True,
                "data": {
                    "screenshot": page_state["screenshot"],
                    "html": page_state["html"]
                },
                "error": ""
            }
        except Exception as e:
            logger.error(f"Error executing action: {str(e)}", exc_info=True)
            return {
                "success": False,
                "data": {},
                "error": str(e)
            }
            
    def _truncate_response(self, response_data: Dict) -> Dict:
        """Helper to truncate large data in responses for logging."""
        return truncate_data(response_data)

    def run_task(self, url: str, goal: str) -> Dict[str, Any]:
        """Run a task with a specific goal."""
        if not self.driver:
            raise RuntimeError("WebDriver not initialized")
            
        try:
            # Navigate to the target URL
            logger.info(f"Navigating to URL: {url}")
            self.driver.get(url)
            
            # Get initial page state
            logger.info("Getting initial page state")
            page_state = self.get_page_state()
            
            # Start task with goal
            logger.info(f"Sending goal request to server at {self.base_url}")
            try:
                # Create request data
                request_data = {
                    "goal": goal,
                    "screenshot": "[TRUNCATED]",  # Don't log the actual data
                    "html": "[TRUNCATED]",        # Don't log the actual data
                    "session_id": int(time.time())
                }
                logger.info(f"Request data: {request_data}")
                
                # Send actual data
                response = requests.post(
                    f"{self.base_url}/api/goal",
                    json={
                        "goal": goal,
                        "screenshot": page_state["screenshot"],
                        "html": page_state["html"],
                        "session_id": int(time.time())
                    }
                )
                
                logger.info(f"Server response status: {response.status_code}")
                logger.info(f"Server response headers: {dict(response.headers)}")
                
                # Log truncated response
                response_json = response.json()
                truncated_response = self._truncate_response(response_json)
                logger.info(f"Server response: {truncated_response}")
                
                if response.status_code != 200:
                    error_msg = f"Failed to start task. Status code: {response.status_code}, Response: {response.text}"
                    logger.error(error_msg)
                    raise RuntimeError(error_msg)
                    
                result = response.json()
                # logger.info(f"Parsed server response: {result}")
                
            except requests.exceptions.ConnectionError as e:
                logger.error(f"Failed to connect to server at {self.base_url}: {str(e)}")
                raise RuntimeError(f"Server connection failed: {str(e)}")
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse server response: {str(e)}")
                logger.error(f"Raw response: {response.text[:500]}...")
                raise RuntimeError(f"Invalid server response: {str(e)}")
            
            # Continue executing actions until task is complete
            while result.get("type") == "action":
                action = result["data"]
                # Truncate action data for logging
                truncated_action = self._truncate_response({"data": action})["data"]
                # logger.info(f"Executing action: {truncated_action}")
                
                # Execute action and get result
                action_result = self.execute_action(action)
                
                # Send action result back to agent
                logger.info("Sending action result to server")
                response = requests.post(
                    f"{self.base_url}/api/action_result",
                    json=action_result
                )
                if response.status_code != 200:
                    error_msg = f"Failed to send action result. Status code: {response.status_code}, Response: {response.text}"
                    logger.error(error_msg)
                    raise RuntimeError(error_msg)
                    
                result = response.json()
                truncated_result = self._truncate_response(result)
                logger.info(f"Server response: {truncated_result}")
                
            return result
        except Exception as e:
            logger.error(f"Error in run_task: {str(e)}", exc_info=True)
            return {
                "success": False,
                "type": "error",
                "error": str(e)
            } 