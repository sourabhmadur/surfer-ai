"""Configuration module for the application."""
from enum import Enum
import os
import logging
from typing import Optional
from dotenv import load_dotenv
from pydantic_settings import BaseSettings

# Load environment variables from .env file
load_dotenv()

class ModelProvider(Enum):
    GEMINI = "gemini"
    OPENAI = "openai"

def setup_logging():
    """Configure logging settings for the application."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Reduce noise from third-party libraries
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    logging.getLogger('openai').setLevel(logging.WARNING)
    logging.getLogger('google').setLevel(logging.WARNING)

class Settings(BaseSettings):
    OPENAI_API_KEY: Optional[str] = None
    GOOGLE_API_KEY: Optional[str] = None  # Note: Changed from GEMINI_API_KEY to match LangChain's expected env var
    MODEL_PROVIDER: ModelProvider = ModelProvider.GEMINI
    
    # Model names
    OPENAI_MODEL: str = "gpt-4o-mini"
    GEMINI_MODEL: str = "gemini-2.0-flash-exp"
    
    class Config:
        env_file = ".env"

settings = Settings() 