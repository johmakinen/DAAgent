"""Intent classification agent."""
from pydantic_ai import Agent, ModelMessage
from typing import Optional, List
from app.core.models import IntentClassification, DatabasePack


class IntentAgent:
    """
    Agent for classifying user intent and determining if clarification is needed.
    """
    
    def __init__(self, model: str, prompt_template: str, database_pack: Optional[DatabasePack] = None):
        """
        Initialize the intent agent.
        
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
            output_type=IntentClassification
        )
    
    async def run(self, user_message: str, message_history: Optional[List[ModelMessage]] = None):
        """
        Run the intent classification agent.
        
        Args:
            user_message: The user's message to classify
            message_history: Optional message history for conversation context
            
        Returns:
            Agent result with IntentClassification output
        """
        if message_history:
            return await self.agent.run(user_message, message_history=message_history)
        else:
            return await self.agent.run(user_message)

