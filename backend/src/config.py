"""Configuration settings for the application."""
from enum import Enum
from typing import Optional, List
import logging
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def setup_logging():
    """Configure logging settings for the application."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Reduce noise from third-party libraries
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)
    logging.getLogger('openai').setLevel(logging.WARNING)
    logging.getLogger('google').setLevel(logging.WARNING)
    logging.getLogger('anthropic').setLevel(logging.WARNING)

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

# Configure logging based on settings
setup_logging()

# Validate required API key is present
if settings.model_provider == ModelProvider.OPENAI and not settings.openai_api_key:
    raise ValueError("OpenAI API key is required when using OpenAI model provider")
elif settings.model_provider == ModelProvider.GOOGLE and not settings.google_api_key:
    raise ValueError("Google API key is required when using Google model provider")
elif settings.model_provider == ModelProvider.ANTHROPIC and not settings.anthropic_api_key:
    raise ValueError("Anthropic API key is required when using Anthropic model provider") 