"""Response formatting utilities for agent outputs."""
from typing import Literal, Optional
from app.core.models import QueryAgentOutput


class ResponseFormatter:
    """Formats agent outputs for synthesizer input."""
    
    @staticmethod
    def format_context_for_synthesizer(
        user_message: str,
        agent_output: Optional[QueryAgentOutput],
        intent_type: Literal["database_query", "general_question"]
    ) -> str:
        """
        Format context for synthesizer based on intent type and agent output.
        
        Args:
            user_message: Original user question
            agent_output: Output from database query agent (None for general questions)
            intent_type: Type of intent that was processed
            
        Returns:
            Formatted context string for synthesizer
            
        Raises:
            ValueError: If agent_output is None for database_query intent
        """
        if intent_type == "database_query":
            if agent_output is None:
                raise ValueError("agent_output must be provided for database_query intent")
            
            query_output: QueryAgentOutput = agent_output
            context = (
                f"User question: {user_message}\n\n"
                f"SQL Query executed: {query_output.sql_query}\n"
                f"Query explanation: {query_output.explanation}\n"
                f"Query success: {query_output.query_result.success}\n"
            )
            
            if query_output.query_result.success:
                if query_output.query_result.row_count == 0:
                    context += "Query returned 0 rows."
                else:
                    # Format first few rows for context
                    rows_str = []
                    for i, row in enumerate(query_output.query_result.data[:5], 1):
                        row_str = ", ".join([f"{k}: {v}" for k, v in row.items()])
                        rows_str.append(f"Row {i}: {row_str}")
                    context += f"Query returned {query_output.query_result.row_count} row(s):\n" + "\n".join(rows_str)
                    if query_output.query_result.row_count > 5:
                        context += f"\n... and {query_output.query_result.row_count - 5} more rows"
            else:
                context += f"Query error: {query_output.query_result.error}"
        else:
            # For general questions, pass the user question directly to synthesizer
            context = f"User question: {user_message}"
        
        return context

