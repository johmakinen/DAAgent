"""Routing utilities for intent-based agent routing."""
from typing import Optional, List, Tuple, Any
from pydantic_ai import ModelMessage
import mlflow
import logging

from app.core.models import QueryAgentOutput
from app.agents.database_query_agent import DatabaseQueryAgent

logger = logging.getLogger(__name__)


class Router:
    """Handles intent-based routing to appropriate agents."""
    
    def __init__(self, database_query_agent: DatabaseQueryAgent):
        """
        Initialize the router.
        
        Args:
            database_query_agent: Database query agent instance
        """
        self.database_query_agent = database_query_agent
        self.max_retries = 2  # Maximum retries (3 total attempts: initial + 2 retries)
    
    def _build_error_context(self, error_msg: str, failed_query: str) -> str:
        """
        Build error context message for retry attempts.
        
        Args:
            error_msg: The error message from the failed query
            failed_query: The SQL query that failed
            
        Returns:
            Error context string to append to user message
        """
        return (
            f"\n\nIMPORTANT: The previous query failed with error: {error_msg}\n"
            f"Failed query: {failed_query}\n"
            f"Please analyze the error, use schema tools if needed to find the correct column/table names, "
            f"generate a corrected query, and execute it using the query_database tool."
        )
    
    async def _execute_query_attempt(
        self,
        user_message: str,
        message_history: Optional[List[ModelMessage]] = None
    ) -> Tuple[QueryAgentOutput, Any]:
        """
        Execute a single database query attempt.
        
        Args:
            user_message: The user's message (may include error context for retries)
            message_history: Optional message history for context
            
        Returns:
            Tuple of (QueryAgentOutput, RunResult) from the agent execution
        """
        run_result = await self.database_query_agent.run(
            user_message,
            message_history=message_history
        )
        return run_result.output, run_result
    
    @mlflow.trace(name="route_to_database_query")
    async def route_to_database_query(
        self, 
        user_message: str, 
        message_history: Optional[List[ModelMessage]] = None
    ) -> Tuple[QueryAgentOutput, Any]:
        """
        Route to database query agent to generate and execute SQL.
        Automatically retries failed queries with error context.
        
        Args:
            user_message: The user's message
            message_history: Optional message history for context
            
        Returns:
            Tuple of (QueryAgentOutput, RunResult) with SQL query and results
        """
        original_message = user_message
        current_message_history = message_history
        last_result = None
        last_run_result = None
        
        # Try up to max_retries + 1 times (initial attempt + retries)
        for attempt in range(self.max_retries + 1):
            # Log attempt number
            if attempt == 0:
                logger.info("LLM Call: DatabaseQueryAgent - initial query attempt")
            else:
                logger.info(f"LLM Call: DatabaseQueryAgent - retry attempt {attempt + 1}")
            
            # Execute a single attempt
            agent_output, run_result = await self._execute_query_attempt(
                user_message,
                current_message_history
            )
            last_result = agent_output
            last_run_result = run_result
            
            # Check if query succeeded
            if agent_output.query_result.success:
                logger.info(f"Database query succeeded on attempt {attempt + 1}")
                return agent_output, run_result
            
            # Query failed - check if we should retry
            if attempt < self.max_retries:
                error_msg = agent_output.query_result.error or "Unknown error"
                failed_query = agent_output.sql_query
                
                logger.warning(
                    f"Database query failed on attempt {attempt + 1}: {error_msg}. "
                    f"Retrying... ({self.max_retries - attempt} retries remaining)"
                )
                
                # Build error context and update message for retry
                error_context = self._build_error_context(error_msg, failed_query)
                user_message = original_message + error_context
                
                # Initialize message history if needed
                if current_message_history is None:
                    current_message_history = []
            else:
                # All retries exhausted
                logger.error(
                    f"Database query failed after {attempt + 1} attempts. "
                    f"Last error: {agent_output.query_result.error}"
                )
        
        # Return the last failed result
        return last_result, last_run_result

