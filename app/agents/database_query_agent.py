"""Database query agent for generating and executing SQL queries."""
import mlflow
from pydantic_ai import Agent, RunContext, ModelMessage
from typing import Optional, List
from pydantic import BaseModel, ConfigDict
from app.core.models import DatabaseQuery, DatabaseResult, QueryAgentOutput, DatabasePack
from app.tools.db_tool import DatabaseTool
from app.tools.schema_tool import SchemaTool

mlflow.pydantic_ai.autolog()


class DatabaseQueryDeps(BaseModel):
    """Dependencies for DatabaseQueryAgent tools."""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    db_tool: DatabaseTool
    schema_tool: Optional[SchemaTool] = None


class DatabaseQueryAgent:
    """
    Agent for generating SQL queries and executing them against the database.
    Uses progressive disclosure - loads schema information on-demand via tools.
    """
    
    def __init__(
        self, 
        model: str, 
        prompt_template: str, 
        db_tool: DatabaseTool, 
        schema_tool: Optional[SchemaTool] = None,
        database_pack: Optional[DatabasePack] = None
    ):
        """
        Initialize the database query agent.
        
        Args:
            model: The model identifier for the agent
            prompt_template: The prompt template/instructions for the agent (no schema included)
            db_tool: The database tool instance for executing queries
            schema_tool: Optional schema tool for loading schema on-demand
            database_pack: Optional database pack (deprecated, kept for compatibility)
        """
        self.db_tool = db_tool
        self.schema_tool = schema_tool
        
        # Note: prompt_template should NOT have schema information - agent loads it via tools
        self.agent = Agent(
            model,
            instructions=prompt_template,
            output_type=QueryAgentOutput,
            deps_type=DatabaseQueryDeps
        )
        
        # Register database tool - tracing is handled in DatabaseTool.execute_query()
        @self.agent.tool
        def query_database(ctx: RunContext[DatabaseQueryDeps], sql_query: str) -> DatabaseResult:
            """
            Execute a SQL query against the database and return results.
            
            Args:
                sql_query: The SQL query to execute (e.g., "SELECT * FROM iris WHERE species = 'setosa'")
            
            Returns:
                DatabaseResult with query results or error information
            """
            db_query = DatabaseQuery(query=sql_query)
            return ctx.deps.db_tool.execute_query(db_query)
        
        # Register schema loading tools (always register, but check for None in implementation)
        @self.agent.tool
        def load_table_schema(ctx: RunContext[DatabaseQueryDeps], table_name: str) -> str:
            """
            Load full schema information for a specific table.
            
            Use this when you need detailed information about a specific table's columns,
            types, descriptions, and relationships before writing a query.
            
            Args:
                table_name: Name of the table to load schema for (e.g., "iris", "postal_code_income")
            
            Returns:
                Formatted string with complete table schema information
            """
            if ctx.deps.schema_tool is None:
                return "Schema tool not available. Cannot load table schema."
            return ctx.deps.schema_tool.load_table_schema(table_name)
        
        @self.agent.tool
        def load_full_schema(ctx: RunContext[DatabaseQueryDeps]) -> str:
            """
            Load the complete database schema with all tables, columns, and relationships.
            
            Use this when you need comprehensive schema information for complex queries
            involving multiple tables or when you're unsure which tables to query.
            
            Returns:
                Formatted string with complete database schema
            """
            if ctx.deps.schema_tool is None:
                return "Schema tool not available. Cannot load full schema."
            return ctx.deps.schema_tool.load_full_schema()
        
        @self.agent.tool
        def list_tables(ctx: RunContext[DatabaseQueryDeps]) -> str:
            """
            Get a list of all available table names.
            
            Use this to discover what tables are available in the database.
            
            Returns:
                Formatted string listing all available tables
            """
            if ctx.deps.schema_tool is None:
                return "Schema tool not available. Cannot list tables."
            return ctx.deps.schema_tool.list_tables()
    
    async def run(self, user_message: str, message_history: Optional[List[ModelMessage]] = None):
        """
        Run the database query agent.
        
        Args:
            user_message: The user's database question
            message_history: Optional message history for conversation context
        
        Returns:
            Agent result with QueryAgentOutput output
        """
        deps = DatabaseQueryDeps(
            db_tool=self.db_tool,
            schema_tool=self.schema_tool
        )
        if message_history:
            return await self.agent.run(user_message, deps=deps, message_history=message_history)
        else:
            return await self.agent.run(user_message, deps=deps)

