"""Base models for browser automation."""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field

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