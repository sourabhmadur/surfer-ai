"""Script to run WebVoyager tasks."""
import sys
import os
import json
import logging
from pathlib import Path

# Add the backend directory to Python path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, backend_dir)

from src.config import setup_logging
from src.tools.selenium_agent import SeleniumAgent

def load_tasks(tasks_file: str) -> list:
    """Load WebVoyager tasks from JSON file."""
    with open(tasks_file, 'r') as f:
        data = json.load(f)
    return data.get('tasks', [])

def main():
    # Setup logging
    setup_logging()
    logger = logging.getLogger(__name__)
    
    # Load tasks
    tasks_file = Path("webvoyager/tasks.json")
    tasks = load_tasks(tasks_file)
    
    # Initialize agent
    agent = SeleniumAgent(url="http://localhost:8000")
    agent.setup()
    
    results = []
    try:
        for task in tasks:
            logger.info(f"\n=== Running Task {task['id']} ===")
            logger.info(f"Goal: {task['goal']}")
            logger.info(f"URL: {task['url']}")
            
            result = agent.run_webvoyager_task(task)
            results.append(result)
            
            # Log task results
            logger.info(f"\n=== Task {task['id']} Results ===")
            logger.info(f"Success: {result['success']}")
            logger.info(f"Metrics: {result['metrics']}")
            if result.get('error'):
                logger.error(f"Error: {result['error']}")
                
    finally:
        agent.teardown()
    
    # Calculate overall metrics
    total_tasks = len(results)
    successful_tasks = sum(1 for r in results if r['success'])
    total_time = sum(r['metrics']['completion_time'] for r in results)
    total_actions = sum(r['metrics']['action_count'] for r in results)
    total_errors = sum(r['metrics']['error_count'] for r in results)
    
    logger.info("\n=== Overall Results ===")
    logger.info(f"Tasks completed: {successful_tasks}/{total_tasks}")
    logger.info(f"Success rate: {(successful_tasks/total_tasks)*100:.2f}%")
    logger.info(f"Average time per task: {total_time/total_tasks:.2f}s")
    logger.info(f"Average actions per task: {total_actions/total_tasks:.2f}")
    logger.info(f"Total errors: {total_errors}")
    
    # Save detailed results
    output_file = Path("webvoyager_results.json")
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    logger.info(f"\nDetailed results saved to: {output_file}")

if __name__ == "__main__":
    main() 