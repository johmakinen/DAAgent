"""Configuration management for the agent system."""
import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv
from pydantic_ai.providers.azure import AzureProvider

load_dotenv()

@dataclass
class AzureModelConfig:
    """Azure model configuration."""
    name: str
    provider: AzureProvider

class Config:
    """Centralized configuration management."""
    
    # Model configuration
    SMALL_MODEL: AzureModelConfig = AzureModelConfig(
        name=os.getenv("SMALL_MODEL_AZURE_NAME"),
        provider=AzureProvider(
            azure_endpoint=os.getenv("SMALL_MODEL_AZURE_ENDPOINT"),
            api_version=os.getenv("SMALL_MODEL_AZURE_API_VERSION"),
            api_key=os.getenv("SMALL_MODEL_AZURE_API_KEY")
        )
    )
    MEDIUM_MODEL: AzureModelConfig = AzureModelConfig(
        name=os.getenv("MEDIUM_MODEL_AZURE_NAME"),
        provider=AzureProvider(
            azure_endpoint=os.getenv("MEDIUM_MODEL_AZURE_ENDPOINT"),
            api_version=os.getenv("MEDIUM_MODEL_AZURE_API_VERSION"),
            api_key=os.getenv("MEDIUM_MODEL_AZURE_API_KEY")
        )
    )

    # MLflow configuration
    MLFLOW_EXPERIMENT_NAME: Optional[str] = os.getenv("MLFLOW_EXPERIMENT_NAME")
    
    # Database pack configuration
    DEFAULT_PACK_PATH: str = os.getenv("DEFAULT_PACK_PATH", "app/packs/database_pack.yaml")
    
    # Server configuration
    PORT: int = int(os.getenv("PORT", 8000))
    HOST: str = os.getenv("HOST", "0.0.0.0")
    
    @classmethod
    def get_model(cls, agent_type: str = "default") -> AzureModelConfig:
        """
        Get model configuration for a specific agent type.
        
        Args:
            agent_type: Type of agent ('queryagent', 'planner', 'synthesizer', 'plot-planning', 'summarizer', 'default')
            
        Returns:
            AzureModelConfig for the specified agent type
        """
        # Map agent types to models
        # if agent_type == "queryagent":
            # return cls.MEDIUM_MODEL
        # All other agents use MEDIUM
        return cls.SMALL_MODEL

