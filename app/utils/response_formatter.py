"""Response formatting utilities for agent outputs."""
from typing import Literal, Optional
from app.core.models import QueryAgentOutput, ExecutionPlan


class ResponseFormatter:
    """Formats agent outputs for synthesizer input."""
    
    @staticmethod
    def format_context_for_synthesizer(
        user_message: str,
        agent_output: Optional[QueryAgentOutput],
        intent_type: Literal["database_query", "general_question"],
        execution_plan: Optional[ExecutionPlan] = None
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
            )
            
            # Indicate if cached data was used
            if execution_plan and execution_plan.use_cached_data:
                context += "Note: Using cached data from a previous query (no new database query executed).\n"
            
            # Indicate if a plot will be generated
            if execution_plan and execution_plan.requires_plot:
                plot_type_name = execution_plan.plot_type or "visualization"
                context += f"Note: A {plot_type_name} plot will be generated to visualize the results.\n"
            
            context += (
                f"SQL Query executed: {query_output.sql_query}\n"
                f"Query explanation: {query_output.explanation}\n"
                f"Query success: {query_output.query_result.success}\n"
            )
            
            if query_output.query_result.success:
                if query_output.query_result.row_count == 0:
                    context += "Query returned 0 rows."
                else:
                    # Include column information and actual data values
                    if query_output.query_result.data:
                        columns = list(query_output.query_result.data[0].keys())
                        # Infer data types
                        sample_row = query_output.query_result.data[0]
                        col_info = []
                        for col in columns:
                            val = sample_row.get(col)
                            if val is not None:
                                if isinstance(val, (int, float)):
                                    col_info.append(f"{col} (numeric)")
                                else:
                                    col_info.append(f"{col} (text)")
                            else:
                                col_info.append(f"{col} (unknown)")
                        
                        row_count = query_output.query_result.row_count
                        context += f"Query returned {row_count} row(s) with columns: {', '.join(col_info)}\n\n"
                        
                        # Optimize data size: for large result sets, include only sample rows
                        MAX_ROWS_TO_INCLUDE = 50
                        SAMPLE_SIZE = 10
                        
                        if row_count > MAX_ROWS_TO_INCLUDE:
                            # Include only first SAMPLE_SIZE rows for large result sets
                            sample_data = query_output.query_result.data[:SAMPLE_SIZE]
                            import json
                            context += f"Query result data (showing first {SAMPLE_SIZE} of {row_count} rows):\n"
                            context += json.dumps(sample_data, indent=2)
                            context += f"\n\nNote: Full dataset ({row_count} rows) is available for plot generation if needed."
                        else:
                            # Include all data for smaller result sets
                            context += "Query result data:\n"
                            import json
                            context += json.dumps(query_output.query_result.data, indent=2)
            else:
                context += f"Query error: {query_output.query_result.error}"
        else:
            # For general questions, pass the user question directly to synthesizer
            context = f"User question: {user_message}"
        
        return context

