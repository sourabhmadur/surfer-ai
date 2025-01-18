from fastapi.testclient import TestClient
from src.main import app

client = TestClient(app)

def test_goal_endpoint():
    response = client.post(
        "/api/goal",
        json={
            "goal": "test goal",
            "screenshot": "base64_encoded_screenshot",
            "html": "<html><body>Test page</body></html>",
            "session_id": 12345
        }
    )
    assert response.status_code == 200
    assert "success" in response.json()

def test_action_result_endpoint():
    response = client.post(
        "/api/action_result",
        json={
            "success": True,
            "data": {
                "screenshot": "base64_encoded_screenshot",
                "html": "<html><body>Updated page</body></html>"
            },
            "error": ""
        }
    )
    print("\nResponse status:", response.status_code)
    print("Response body:", response.json())
    assert response.status_code == 200
    assert "success" in response.json() 