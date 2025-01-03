"""LLM provider module."""
import logging
from typing import Optional
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from config import settings, ModelProvider

logger = logging.getLogger(__name__)

class LLMProvider:
    """Provider for LLM models."""
    
    _instance: Optional[ChatGoogleGenerativeAI | ChatOpenAI | ChatAnthropic] = None
    
    @classmethod
    def get_llm(cls):
        """Get LLM instance."""
        if cls._instance is None:
            logger.info(f"Initializing LLM with provider: {settings.model_provider}")
            
            if settings.model_provider == ModelProvider.GOOGLE:
                cls._instance = ChatGoogleGenerativeAI(
                    model=settings.model_name,
                    temperature=settings.temperature,
                    max_output_tokens=settings.max_tokens,
                    convert_system_message_to_human=True,
                    google_api_key=settings.google_api_key
                )
            elif settings.model_provider == ModelProvider.OPENAI:
                cls._instance = ChatOpenAI(
                    model=settings.model_name,
                    temperature=settings.temperature,
                    max_tokens=settings.max_tokens,
                    openai_api_key=settings.openai_api_key
                )
            elif settings.model_provider == ModelProvider.ANTHROPIC:
                cls._instance = ChatAnthropic(
                    model=settings.model_name,
                    temperature=settings.temperature,
                    max_tokens=settings.max_tokens,
                    anthropic_api_key=settings.anthropic_api_key
                )
            else:
                raise ValueError(f"Unsupported model provider: {settings.model_provider}")
            
            logger.info("LLM initialized successfully")
        
        return cls._instance 