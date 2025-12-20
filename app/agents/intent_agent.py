"""Intent classification agent."""
from pydantic_ai import Agent
from app.core.models import IntentClassification


class IntentAgent:
    """
    Agent for classifying user intent and determining if clarification is needed.
    """
    
    def __init__(self, model: str, prompt_template: str):
        """
        Initialize the intent agent.
        
        Args:
            model: The model identifier for the agent
            prompt_template: The prompt template/instructions for the agent
        """
        self.agent = Agent(
            model,
            instructions=prompt_template,
            output_type=IntentClassification
        )
    
    async def run(self, user_message: str):
        """
        Run the intent classification agent.
        
        Args:
            user_message: The user's message to classify
            
        Returns:
            Agent result with IntentClassification output
        """
        return await self.agent.run(user_message)

