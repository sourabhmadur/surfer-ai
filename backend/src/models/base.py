"""Base models for browser automation."""
from typing import List, Dict, Any, Optional, Literal
from datetime import datetime
import logging
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

class Message(BaseModel):
    """Represents a message in the conversation."""
    role: str
    content: str

class Observation(BaseModel):
    """Represents a single observation of the browser state."""
    screenshot: str = Field(...)
    html: str = Field(...)
    timestamp: datetime = Field(default_factory=datetime.now)

class BrowserState(BaseModel):
    """State for browser automation."""
    messages: List[Message] = Field(default_factory=list)
    goal: str = Field(..., min_length=1)
    session_id: int = Field(...)
    last_action_result: Optional[Dict[str, Any]] = None
    past_actions: List[Dict[str, Any]] = Field(default_factory=list)  # Store past actions
    observations: List[Observation] = Field(default_factory=list)
    max_observations: Literal[3] = Field(default=3)  # Using Literal instead of const

    @property
    def page_state(self) -> Dict[str, Any]:
        """Get the most recent page state."""
        if not self.observations:
            return {"screenshot": "", "html": ""}
        latest = self.observations[-1]
        return {
            "screenshot": latest.screenshot,
            "html": latest.html
        }

    @page_state.setter
    def page_state(self, value: Dict[str, Any]) -> None:
        """Add a new observation while maintaining the history limit."""
        if not isinstance(value, dict):
            raise ValueError("page_state must be a dictionary")

        logger.info(f"[page_state setter] Adding new observation. Current observations count: {len(self.observations)}")
        logger.info(f"[page_state setter] Value contains screenshot: {bool(value.get('screenshot'))}, html: {bool(value.get('html'))}")
        
        # Only add new observation if it contains valid data
        if value.get("screenshot") or value.get("html"):
            new_observation = Observation(
                screenshot=value.get("screenshot", ""),
                html=value.get("html", "")
            )
            
            # Add the new observation
            self.observations.append(new_observation)
            logger.info(f"[page_state setter] Observation added. New count: {len(self.observations)}")
            logger.info(f"[page_state setter] Timestamps: {[obs.timestamp for obs in self.observations]}")
            
            # Keep only the most recent observations
            if len(self.observations) > self.max_observations:
                logger.info(f"[page_state setter] Trimming observations from {len(self.observations)} to {self.max_observations}")
                self.observations = self.observations[-self.max_observations:]
                logger.info(f"[page_state setter] Final observations count: {len(self.observations)}")
                logger.info(f"[page_state setter] Final timestamps: {[obs.timestamp for obs in self.observations]}")
        else:
            logger.warning("[page_state setter] Skipping observation update - no valid screenshot or HTML data") 