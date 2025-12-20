"""Configuration management for the agent system."""
import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Centralized configuration management."""
    
    # Model configuration
    DEFAULT_MODEL: str = os.getenv("DEFAULT_MODEL", "azure:gpt-5-nano")
    SUMMARIZER_MODEL: str = os.getenv("SUMMARIZER_MODEL", "azure:gpt-5-nano")
    
    # MLflow configuration
    MLFLOW_EXPERIMENT_NAME: Optional[str] = os.getenv("MLFLOW_EXPERIMENT_NAME")
    
    # Database pack configuration
    DEFAULT_PACK_PATH: str = os.getenv("DEFAULT_PACK_PATH", "app/packs/iris_database.yaml")
    
    # Server configuration
    PORT: int = int(os.getenv("PORT", 8000))
    HOST: str = os.getenv("HOST", "0.0.0.0")
    
    @classmethod
    def get_model(cls, agent_type: str = "default") -> str:
        """
        Get model identifier for a specific agent type.
        
        Args:
            agent_type: Type of agent ('default', 'summarizer')
            
        Returns:
            Model identifier string
        """
        if agent_type == "summarizer":
            return cls.SUMMARIZER_MODEL
        return cls.DEFAULT_MODEL

