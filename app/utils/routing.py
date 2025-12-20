"""Routing utilities for intent-based agent routing."""
from typing import Optional, List, Tuple, Any
from pydantic_ai import ModelMessage
import mlflow

from app.core.models import QueryAgentOutput
from app.agents.database_query_agent import DatabaseQueryAgent


class Router:
    """Handles intent-based routing to appropriate agents."""
    
    def __init__(self, database_query_agent: DatabaseQueryAgent):
        """
        Initialize the router.
        
        Args:
            database_query_agent: Database query agent instance
        """
        self.database_query_agent = database_query_agent
    
    @mlflow.trace(name="route_to_database_query")
    async def route_to_database_query(
        self, 
        user_message: str, 
        message_history: Optional[List[ModelMessage]] = None
    ) -> Tuple[QueryAgentOutput, Any]:
        """
        Route to database query agent to generate and execute SQL.
        
        Args:
            user_message: The user's message
            message_history: Optional message history for context
            
        Returns:
            Tuple of (QueryAgentOutput, RunResult) with SQL query and results
        """
        result = await self.database_query_agent.run(user_message, message_history=message_history)
        return result.output, result

