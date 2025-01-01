class ExecutorTool:
    def __init__(self, browser_controller):
        self.browser_controller = browser_controller

    def parse_action(self, action_str):
        action_str = action_str.strip().lower()
        
        # Handle scroll actions
        if action_str.startswith("scroll"):
            direction = "down" if "down" in action_str else "up"
            pixels = int(''.join(filter(str.isdigit, action_str)))
            return {
                "type": "scroll",
                "direction": direction,
                "pixels": pixels
            }
        
        # Handle click actions
        elif action_str.startswith("click"):
            element_desc = action_str[action_str.index("on ") + 3:].strip()
            return {
                "type": "click",
                "element": element_desc
            }
        
        # Handle type actions
        elif action_str.startswith("type"):
            text = action_str[5:].strip()  # Remove "type " prefix
            return {
                "type": "type",
                "text": text
            }
        
        raise ValueError(f"Invalid action format: {action_str}")

    async def execute(self, action_str):
        try:
            action = self.parse_action(action_str)
            
            if action["type"] == "scroll":
                return await self.browser_controller.scroll(
                    action["direction"],
                    action["pixels"]
                )
            
            elif action["type"] == "click":
                return await self.browser_controller.click(action["element"])
            
            elif action["type"] == "type":
                return await self.browser_controller.type_text(action["text"])
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            } 