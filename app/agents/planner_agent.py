"""Planner agent for creating execution plans."""
from pydantic_ai import Agent, ModelMessage
from typing import Optional, List
from app.core.models import ExecutionPlan, DatabasePack


class PlannerAgent:
    """
    Agent for creating structured execution plans that determine intent, plot requirements,
    and whether to use cached data or fetch new data.
    """
    
    def __init__(self, model: str, prompt_template: str, database_pack: Optional[DatabasePack] = None):
        """
        Initialize the planner agent.
        
        Args:
            model: The model identifier for the agent
            prompt_template: The prompt template/instructions for the agent (pack should already be injected)
            database_pack: Optional database pack (kept for future use, currently template is pre-injected)
        """
        # Note: prompt_template should already have pack information injected by PromptRegistry
        # The database_pack parameter is kept for potential future direct use by the agent
        self.agent = Agent(
            model,
            instructions=prompt_template,
            output_type=ExecutionPlan
        )
    
    async def run(self, user_message: str, message_history: Optional[List[ModelMessage]] = None):
        """
        Run the planner agent to create an execution plan.
        
        Args:
            user_message: The user's message to plan for
            message_history: Optional message history for conversation context
            
        Returns:
            Agent result with ExecutionPlan output
        """
        if message_history:
            return await self.agent.run(user_message, message_history=message_history)
        else:
            return await self.agent.run(user_message)
