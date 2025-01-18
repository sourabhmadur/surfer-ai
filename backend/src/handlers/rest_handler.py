"""REST API handler for browser automation."""
from typing import Dict, Any
import logging
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from handlers.base_handler import BaseHandler
from src.utils.logging import truncate_data

# Get logger with the full module path
logger = logging.getLogger("src.handlers.rest_handler")

class GoalRequest(BaseModel):
    """Request model for goal endpoint."""
    goal: str
    screenshot: str
    html: str
    session_id: int

class ActionResult(BaseModel):
    """Request model for action result endpoint."""
    success: bool
    data: Dict[str, Any]
    error: str = None

router = APIRouter()
handler = BaseHandler()

def _clean_data_for_logging(data: Dict[str, Any]) -> Dict[str, Any]:
    """Clean sensitive data before logging."""
    if not isinstance(data, dict):
        return data
        
    clean_data = {}
    for key, value in data.items():
        if isinstance(value, dict):
            clean_data[key] = _clean_data_for_logging(value)
        elif key in ['html', 'screenshot', 'page_state']:
            clean_data[key] = '[REDACTED]'
        else:
            clean_data[key] = value
    return clean_data

@router.post("/goal")
async def handle_goal(request: GoalRequest) -> Dict[str, Any]:
    """Handle new goal request."""
    try:
        # Log sanitized version of request
        clean_request = _clean_data_for_logging(request.dict())
        logger.info(f"REST handler received goal request: {truncate_data(clean_request)}")
        
        result = await handler.handle_goal(
            goal=request.goal,
            screenshot=request.screenshot,
            html=request.html,
            session_id=request.session_id
        )
        
        logger.info(f"REST handler goal response: {truncate_data(result)}")
        return result
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"REST handler error processing goal request: {error_msg}", exc_info=True)
        raise HTTPException(status_code=500, detail=error_msg)

@router.post("/action_result")
async def handle_action_result(result: ActionResult) -> Dict[str, Any]:
    """Handle action result."""
    try:
        # Log sanitized version of result
        clean_result = _clean_data_for_logging(result.dict())
        # logger.info(f"REST handler received action result: {truncate_data(clean_result)}")
        
        response = await handler.handle_action_result({
            "success": result.success,
            "data": result.data,
            "error": result.error
        })
        
        logger.info(f"REST handler action result response: {truncate_data(response)}")
        return response
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"REST handler error processing action result: {error_msg}", exc_info=True)
        raise HTTPException(status_code=500, detail=error_msg) 