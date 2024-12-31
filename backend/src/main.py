from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from starlette.middleware.cors import CORSMiddleware
from workflow import Agent, create_initial_state
import logging
import json

app = FastAPI()

# Configure logging to filter sensitive data
class SensitiveDataFilter(logging.Filter):
    def filter(self, record):
        if hasattr(record, 'msg'):
            if isinstance(record.msg, str):
                if len(record.msg) > 1000 or 'data:image' in record.msg:
                    record.msg = '[BINARY_DATA_FILTERED]'
            elif isinstance(record.msg, dict):
                filtered_dict = self._filter_dict(record.msg)
                record.msg = filtered_dict
        return True

    def _filter_dict(self, d):
        if not isinstance(d, dict):
            return d
        return {k: '[BINARY_DATA_FILTERED]' if isinstance(v, (str, bytes)) and (len(str(v)) > 1000 or (isinstance(v, str) and 'data:image' in v))
                else self._filter_dict(v) if isinstance(v, dict)
                else v
                for k, v in d.items()}

# Set up logging
logger = logging.getLogger(__name__)
logger.addFilter(SensitiveDataFilter())

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.websocket("/ws/agent")
async def agent_endpoint(websocket: WebSocket):
    logger.info("New WebSocket connection received")
    await websocket.accept()

    # Keep track of current agent and state
    current_agent = None
    current_state = None

    try:
        while True:
            message = await websocket.receive_json()
            logger.info(f"Received message type: {message.get('type')}")

            if message.get("type") == "test":
                logger.info("Received test message")
                await websocket.send_json({"type": "test", "data": "Connection test successful"})
                continue

            # Handle new task
            if "goal" in message:
                # Extract required fields
                goal = message.get("goal")
                session_id = message.get("session_id")
                screenshot = message.get("screenshot")
                html = message.get("html")
                logger.info(f"Received task - Goal: {goal}, Session ID: {session_id}")

                if not all([goal, screenshot, html, session_id]):
                    logger.error("Missing required fields in message")
                    await websocket.send_json({
                        "type": "error",
                        "data": "Missing required fields: goal, screenshot, html, and session_id"
                    })
                    continue

                try:
                    # Initialize agent and state
                    current_agent = Agent()
                    current_state = create_initial_state(session_id, goal, screenshot, html)
                    logger.info("Agent and initial state created")

                    # Execute agent
                    result = current_agent.execute(current_state)
                    logger.info(f"Agent execution result: {result['type']}")

                    # Handle result based on type
                    if result["type"] == "action":
                        # Send action data
                        await websocket.send_json({
                            "type": "action",
                            "data": result["data"]
                        })
                        # Send follow-up message if available
                        if "message" in result:
                            await websocket.send_json({
                                "type": "message",
                                "data": result["message"]
                            })
                    elif result["type"] == "complete":
                        await websocket.send_json({
                            "type": "complete",
                            "data": result["data"]
                        })
                        current_agent = None
                        current_state = None
                    else:  # error
                        await websocket.send_json({
                            "type": "error",
                            "data": result["data"]
                        })
                        current_agent = None
                        current_state = None

                except Exception as e:
                    logger.error(f"Error during agent execution: {str(e)}", exc_info=True)
                    await websocket.send_json({
                        "type": "error",
                        "data": f"Error: {str(e)}"
                    })
                    current_agent = None
                    current_state = None

            # Handle action result
            elif message.get("success") is not None and current_agent and current_state:
                logger.info("Received action result")
                
                if message.get("success"):
                    # Update state with new page state
                    current_state.page_state = {
                        "screenshot": message.get("data", {}).get("screenshot"),
                        "html": message.get("data", {}).get("html")
                    }
                    
                    # Continue agent execution
                    try:
                        result = current_agent.execute(current_state)
                        logger.info(f"Agent execution result: {result['type']}")

                        # Handle result based on type
                        if result["type"] == "action":
                            await websocket.send_json({
                                "type": "action",
                                "data": result["data"]
                            })
                            if "message" in result:
                                await websocket.send_json({
                                    "type": "message",
                                    "data": result["message"]
                                })
                        elif result["type"] == "complete":
                            await websocket.send_json({
                                "type": "complete",
                                "data": result["data"]
                            })
                            current_agent = None
                            current_state = None
                        else:  # error
                            await websocket.send_json({
                                "type": "error",
                                "data": result["data"]
                            })
                            current_agent = None
                            current_state = None

                    except Exception as e:
                        logger.error(f"Error during agent execution: {str(e)}", exc_info=True)
                        await websocket.send_json({
                            "type": "error",
                            "data": f"Error: {str(e)}"
                        })
                        current_agent = None
                        current_state = None
                else:
                    # Handle action failure
                    error_message = message.get("error", "Unknown error during action execution")
                    logger.error(f"Action failed: {error_message}")
                    await websocket.send_json({
                        "type": "error",
                        "data": error_message
                    })
                    current_agent = None
                    current_state = None

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True) 