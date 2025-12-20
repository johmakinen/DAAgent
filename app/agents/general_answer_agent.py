"""General answer agent for non-database questions."""
from pydantic_ai import Agent, ModelMessage
from typing import Optional, List
from app.core.models import GeneralAnswerOutput


class GeneralAnswerAgent:
    """
    Agent for answering general questions that don't require database access.
    """
    
    def __init__(self, model: str, prompt_template: str):
        """
        Initialize the general answer agent.
        
        Args:
            model: The model identifier for the agent
            prompt_template: The prompt template/instructions for the agent
        """
        self.agent = Agent(
            model,
            instructions=prompt_template,
            output_type=GeneralAnswerOutput
        )
    
    async def run(self, user_message: str, message_history: Optional[List[ModelMessage]] = None):
        """
        Run the general answer agent.
        
        Args:
            user_message: The user's question to answer
            message_history: Optional message history for conversation context
            
        Returns:
            Agent result with GeneralAnswerOutput output
        """
        if message_history:
            return await self.agent.run(user_message, message_history=message_history)
        else:
            return await self.agent.run(user_message)

