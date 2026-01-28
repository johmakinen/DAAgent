"""Database query agent for generating and executing SQL queries."""
from pydantic_ai import Agent, RunContext, ModelMessage
from typing import Optional, List
from app.core.models import DatabaseQuery, DatabaseResult, QueryAgentOutput, DatabasePack
from app.tools.db_tool import DatabaseTool


class DatabaseQueryAgent:
    """
    Agent for generating SQL queries and executing them against the database.
    """
    
    def __init__(self, model: str, prompt_template: str, db_tool: DatabaseTool, database_pack: Optional[DatabasePack] = None):
        """
        Initialize the database query agent.
        
        Args:
            model: The model identifier for the agent
            prompt_template: The prompt template/instructions for the agent (pack should already be injected)
            db_tool: The database tool instance for executing queries
            database_pack: Optional database pack (kept for future use, currently template is pre-injected)
        """
        self.db_tool = db_tool
        
        # Note: prompt_template should already have pack information injected by PromptRegistry
        # The database_pack parameter is kept for potential future direct use by the agent
        self.agent = Agent(
            model,
            instructions=prompt_template,
            output_type=QueryAgentOutput,
            deps_type=DatabaseTool
        )
        
        # Register database tool - tracing is handled in DatabaseTool.execute_query()
        @self.agent.tool
        def query_database(ctx: RunContext[DatabaseTool], sql_query: str) -> DatabaseResult:
            """
            Execute a SQL query against the database and return results.
            
            Args:
                sql_query: The SQL query to execute (e.g., "SELECT * FROM iris WHERE species = 'setosa'")
            
            Returns:
                DatabaseResult with query results or error information
            """
            db_query = DatabaseQuery(query=sql_query)
            return ctx.deps.execute_query(db_query)
    
    async def run(self, user_message: str, message_history: Optional[List[ModelMessage]] = None):
        """
        Run the database query agent.
        
        Args:
            user_message: The user's database question
            message_history: Optional message history for conversation context
            
        Returns:
            Agent result with QueryAgentOutput output
        """
        if message_history:
            return await self.agent.run(user_message, deps=self.db_tool, message_history=message_history)
        else:
            return await self.agent.run(user_message, deps=self.db_tool)

