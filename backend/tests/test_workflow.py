import pytest
from backend.src.workflow import WebAutomationWorkflow

pytestmark = pytest.mark.asyncio

@pytest.fixture
def workflow():
    return WebAutomationWorkflow()

def test_scroll_action_parsing():
    workflow = Workflow()  # Adjust based on your actual initialization
    
    # Test scroll down
    result = workflow.planner("scroll down by 300 pixels")
    assert result == {
        "action": "scroll",
        "direction": "down",
        "pixels": 300
    }
    
    # Test scroll up
    result = workflow.planner("scroll up by 200 pixels")
    assert result == {
        "action": "scroll",
        "direction": "up",
        "pixels": 200
    }

# ... rest of the file stays the same ... 