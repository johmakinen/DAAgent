"""Database query agent for generating and executing SQL queries."""
from pydantic_ai import Agent, RunContext
import mlflow
from app.core.models import DatabaseQuery, DatabaseResult, QueryAgentOutput
from app.tools.db_tool import DatabaseTool


class DatabaseQueryAgent:
    """
    Agent for generating SQL queries and executing them against the database.
    """
    
    def __init__(self, model: str, prompt_template: str, db_tool: DatabaseTool):
        """
        Initialize the database query agent.
        
        Args:
            model: The model identifier for the agent
            prompt_template: The prompt template/instructions for the agent
            db_tool: The database tool instance for executing queries
        """
        self.db_tool = db_tool
        self.agent = Agent(
            model,
            instructions=prompt_template,
            output_type=QueryAgentOutput,
            deps_type=DatabaseTool
        )
        
        # Register database tool for query agent
        @mlflow.trace(name="query_database")
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
    
    async def run(self, user_message: str):
        """
        Run the database query agent.
        
        Args:
            user_message: The user's database question
            
        Returns:
            Agent result with QueryAgentOutput output
        """
        return await self.agent.run(user_message, deps=self.db_tool)

