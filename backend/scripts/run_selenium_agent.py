"""Script to run Selenium agent with proper logging."""
import sys
import os
import logging
from pathlib import Path

# Add the backend directory to Python path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from src.config import setup_logging, get_log_file, get_or_create_log_file

def main():
    """Run the Selenium agent with proper logging configuration."""
    # Get or create log file
    log_file = get_or_create_log_file()
    setup_logging()
    

    logger = logging.getLogger(__name__)
    logger.info(f"Using log file: {log_file}")
    logger.info("Starting Selenium agent")
    
    # Only import after logging is configured
    from src.tools.selenium_agent import SeleniumAgent

    # Initialize the agent
    agent = SeleniumAgent(url="http://localhost:8000")
    agent.setup()
    
    
    try:
        # Example task: Navigate and interact with Hacker News
        logger.info("Starting task execution")
        result = agent.run_task(
            url="https://arxiv.org/",
            goal="Search 'Poly encoder' by title on ArXiv and check whether the articles in the search results provide HTML access."
        )
        

        # Log the result
        logger.info("Task completed")
        logger.info(f"Status: {'Success' if result.get('type') == 'complete' else 'Failed'}")
        if result.get("error"):
            logger.error(f"Error: {result['error']}")
            
    except Exception as e:
        logger.error(f"Error running task: {str(e)}", exc_info=True)
        raise
    finally:
        # Always clean up
        logger.info("Cleaning up Selenium agent")
        agent.teardown()

if __name__ == "__main__":
    main() 