"""Synthesizer agent for creating final user-facing responses."""
from pydantic_ai import Agent, ModelMessage
from typing import Optional, List
from app.core.models import AgentResponse


class SynthesizerAgent:
    """
    Agent for synthesizing clear, natural language responses from agent outputs.
    """
    
    def __init__(self, model: str, prompt_template: str):
        """
        Initialize the synthesizer agent.
        
        Args:
            model: The model identifier for the agent
            prompt_template: The prompt template/instructions for the agent
        """
        self.agent = Agent(
            model,
            instructions=prompt_template,
            output_type=AgentResponse
        )
    
    async def run(self, context: str, message_history: Optional[List[ModelMessage]] = None):
        """
        Run the synthesizer agent.
        
        Args:
            context: The context containing agent output to synthesize
            message_history: Optional message history for conversation context
            
        Returns:
            Agent result with AgentResponse output
        """
        if message_history:
            return await self.agent.run(context, message_history=message_history)
        else:
            return await self.agent.run(context)

