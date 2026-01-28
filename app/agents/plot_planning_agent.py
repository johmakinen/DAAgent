"""Plot planning agent for determining plot configuration from user questions."""
import mlflow
import logging
from pydantic_ai import Agent, ModelMessage
from pydantic_ai.models.openai import OpenAIChatModel
from typing import Optional, List, Dict, Any
from app.core.models import PlotConfig, DatabasePack
from app.core.agent_deps import EmptyDeps
from app.core.config import Config

mlflow.pydantic_ai.autolog()

logger = logging.getLogger(__name__)
class PlotPlanningAgent:
    """
    Agent for analyzing user questions and data structure to determine optimal plot configuration.
    Determines which columns to use, whether grouping is needed, and which column to use for grouping/color encoding.
    """
    
    def __init__(self, prompt_template: str, database_pack: Optional[DatabasePack] = None):
        """
        Initialize the plot planning agent.
        
        Args:
            prompt_template: The prompt template/instructions for the agent (pack should already be injected)
            database_pack: Optional database pack (kept for future use, currently template is pre-injected)
        """
        # Note: prompt_template should already have pack information injected by PromptRegistry
        # The database_pack parameter is kept for potential future direct use by the agent
        
        # Get model configuration for this agent
        model_config = Config.get_model('plot-planning')
        
        # Convert AzureModelConfig to OpenAIChatModel
        model = OpenAIChatModel(
            model_config.name,
            provider=model_config.provider,
        )
        
        self.agent = Agent(
            model,
            instructions=prompt_template,
            output_type=PlotConfig,
            deps_type=EmptyDeps,
            name="plot-planning-agent"
        )
    
    async def run(
        self,
        question: str,
        available_columns: List[str],
        column_types: Dict[str, str],
        message_history: Optional[List[ModelMessage]] = None
    ):
        """
        Run the plot planning agent to determine plot configuration.
        
        Args:
            question: The user's question about the plot
            available_columns: List of column names available in the data
            column_types: Dictionary mapping column names to types ('quantitative' or 'nominal')
            message_history: Optional message history for conversation context
            
        Returns:
            Agent result with PlotConfig output
        """
        # Build context for the agent
        col_info = []
        for col in available_columns:
            col_type = column_types.get(col, "unknown")
            col_info.append(f"- {col} ({col_type})")
        
        context = f"""User question: {question}

Available columns and their types:
{chr(10).join(col_info)}

Analyze the user's question and determine the appropriate plot configuration. Consider:
1. Which columns should be used for the plot
2. Whether grouping/color encoding is needed (e.g., "for the three species", "by species", "across categories")
3. Which column should be used for grouping if needed
4. Appropriate x and y column assignments based on the plot type

Match column names mentioned in the question to the available columns, handling variations like plurals, articles, and partial matches."""
        
        logger.info("LLM Call: PlotPlanningAgent - determining plot configuration")
        deps = EmptyDeps()
        if message_history:
            return await self.agent.run(context, deps=deps, message_history=message_history)
        else:
            return await self.agent.run(context, deps=deps)
