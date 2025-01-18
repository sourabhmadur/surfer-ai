"""Configuration settings for the application."""
from enum import Enum
from typing import Optional, List
import logging
import os
from datetime import datetime
from pathlib import Path
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def get_log_file() -> Path:
    """Get a new log file path with timestamp."""
    base_dir = Path(__file__).resolve().parent.parent
    logs_dir = base_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    
    # Use full timestamp for unique log files
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return logs_dir / f"backend_{timestamp}.log"

def get_or_create_log_file() -> Path:
    """Get existing log file path or create a new one."""
    lock_file = Path(__file__).resolve().parent.parent / "logs" / ".current_log"
    
    try:
        # Try to read existing log file path
        if lock_file.exists():
            with open(lock_file, 'r') as f:
                existing_log = Path(f.read().strip())
                if existing_log.exists():
                    return existing_log
    except Exception:
        pass
    
    # Create new log file
    log_file = get_log_file()
    
    # Save the path
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_file, 'w') as f:
        f.write(str(log_file))
    
    return log_file

def setup_logging():
    """Configure logging settings for the application."""
    try:
        # Get the log file path
        log_file = get_or_create_log_file()

        # Configure logging format
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        date_format = '%Y-%m-%d %H:%M:%S'

        # Remove any existing handlers
        root_logger = logging.getLogger()
        root_logger.handlers.clear()

        # Create handlers with write mode to create new file
        file_handler = logging.FileHandler(log_file, encoding='utf-8', mode='w')
        console_handler = logging.StreamHandler()

        # Set formatter for both handlers
        formatter = logging.Formatter(log_format, date_format)
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        # Configure root logger
        root_logger.setLevel(logging.DEBUG)
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)

        # Configure specific loggers
        loggers_to_configure = [
            "uvicorn",
            "uvicorn.access",
            "fastapi",
            "src",
            "selenium",
            "urllib3",
            "websockets",
            "__main__",
            "llm"
        ]

        for logger_name in loggers_to_configure:
            logger = logging.getLogger(logger_name)
            logger.handlers.clear()
            logger.addHandler(file_handler)
            logger.addHandler(console_handler)
            logger.propagate = False
            logger.setLevel(logging.DEBUG)

        # Set levels for noisy loggers
        logging.getLogger('httpx').setLevel(logging.WARNING)
        logging.getLogger('httpcore').setLevel(logging.WARNING)
        logging.getLogger('openai').setLevel(logging.WARNING)
        logging.getLogger('google').setLevel(logging.WARNING)
        logging.getLogger('anthropic').setLevel(logging.WARNING)
        logging.getLogger('urllib3').setLevel(logging.WARNING)
        logging.getLogger('selenium').setLevel(logging.INFO)

        # Log initial setup message
        logging.getLogger(__name__).info(f"Logging initialized in file: {log_file}")
        
        return log_file  # Return the log file path for reference
        
    except Exception as e:
        print(f"Error setting up logging: {str(e)}")
        raise

class ModelProvider(str, Enum):
    """Supported LLM model providers."""
    OPENAI = "openai"
    GOOGLE = "google"
    ANTHROPIC = "anthropic"

    @classmethod
    def _missing_(cls, value: str):
        """Handle legacy 'gemini' value by mapping it to GOOGLE."""
        if value.lower() == "gemini":
            return cls.GOOGLE
        return None

class Settings(BaseSettings):
    """Application settings."""
    # API Keys
    openai_api_key: Optional[str] = None
    google_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    
    # Model Configuration
    model_provider: ModelProvider = ModelProvider.GOOGLE
    
    # Model names per provider
    openai_model: str = "gpt-4-vision-preview"
    gemini_model: str = "gemini-pro-vision"
    anthropic_model: str = "claude-3-opus"
    
    @property
    def model_name(self) -> str:
        """Get the appropriate model name based on the provider."""
        if self.model_provider == ModelProvider.OPENAI:
            return self.openai_model
        elif self.model_provider == ModelProvider.GOOGLE:
            return self.gemini_model
        elif self.model_provider == ModelProvider.ANTHROPIC:
            return self.anthropic_model
        else:
            raise ValueError(f"Unsupported model provider: {self.model_provider}")
    
    # Model parameters
    temperature: float = 0.7
    max_tokens: int = 1000
    
    # Database Configuration
    database_url: str = "sqlite:///./surfer_ai.db"
    
    # CORS Configuration
    cors_origins: str = "chrome-extension://your_extension_id_here"
    
    # Logging
    log_level: str = "INFO"
    
    class Config:
        """Pydantic settings configuration."""
        env_file = ".env"
        case_sensitive = False
        env_file_encoding = 'utf-8'
        extra = "allow"

# Create settings instance
settings = Settings()

# Don't call setup_logging here since it will be called by the entry points

# Validate required API key is present
if settings.model_provider == ModelProvider.OPENAI and not settings.openai_api_key:
    raise ValueError("OpenAI API key is required when using OpenAI model provider")
elif settings.model_provider == ModelProvider.GOOGLE and not settings.google_api_key:
    raise ValueError("Google API key is required when using Google model provider")
elif settings.model_provider == ModelProvider.ANTHROPIC and not settings.anthropic_api_key:
    raise ValueError("Anthropic API key is required when using Anthropic model provider") 