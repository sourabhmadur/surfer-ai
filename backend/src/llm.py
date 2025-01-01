"""LLM provider module."""
from typing import Optional
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI
from config import settings, ModelProvider

class LLMProvider:
    """Provider for LLM instances."""
    
    _instance = None
    
    @classmethod
    def get_llm(cls):
        """Get LLM instance based on configuration."""
        if cls._instance is None:
            if settings.MODEL_PROVIDER == ModelProvider.OPENAI:
                if not settings.OPENAI_API_KEY:
                    raise ValueError("OPENAI_API_KEY not set in environment")
                cls._instance = ChatOpenAI(
                    model=settings.OPENAI_MODEL,
                    temperature=0,
                    api_key=settings.OPENAI_API_KEY,
                    max_tokens=1000
                )
            elif settings.MODEL_PROVIDER == ModelProvider.GEMINI:
                if not settings.GOOGLE_API_KEY:
                    raise ValueError("GOOGLE_API_KEY not set in environment")
                cls._instance = ChatGoogleGenerativeAI(
                    model=settings.GEMINI_MODEL,
                    temperature=0,
                    google_api_key=settings.GOOGLE_API_KEY,
                    convert_system_message_to_human=True
                )
            else:
                raise ValueError(f"Unsupported model provider: {settings.MODEL_PROVIDER}")
        
        return cls._instance
    
    @classmethod
    def reset(cls):
        """Reset the LLM instance."""
        cls._instance = None 