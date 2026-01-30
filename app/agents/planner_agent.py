"""Planner agent for creating execution plans."""
import mlflow
import logging
import asyncio
from pydantic_ai import Agent, RunContext, ModelMessage
from pydantic_ai.models.openai import OpenAIChatModel
from typing import Optional, List, Union
from pydantic import BaseModel, ConfigDict
from app.core.models import ExecutionPlan, DatabasePack
from app.core.config import Config
from app.tools.schema_tool import SchemaTool

mlflow.pydantic_ai.autolog()

logger = logging.getLogger(__name__)


class PlannerDeps(BaseModel):
    """Dependencies for PlannerAgent tools."""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    schema_tool: Optional[SchemaTool] = None
    cancellation_event: Optional[asyncio.Event] = None


class PlannerAgent:
    """
    Agent for creating structured execution plans that determine intent, plot requirements,
    and whether to use cached data or fetch new data.
    """
    
    def __init__(
        self, 
        prompt_template: str, 
        database_pack: Optional[DatabasePack] = None,
        schema_tool: Optional[SchemaTool] = None
    ):
        """
        Initialize the planner agent.
        
        Args:
            prompt_template: The prompt template/instructions for the agent (pack should already be injected)
            database_pack: Optional database pack (kept for future use, currently template is pre-injected)
            schema_tool: Optional schema tool for accessing table descriptions
        """
        # Note: prompt_template should already have pack information injected by PromptRegistry
        # The database_pack parameter is kept for potential future direct use by the agent
        self.schema_tool = schema_tool
        
        # Get model configuration for this agent
        model_config = Config.get_model('planner')
        
        # Convert AzureModelConfig to OpenAIChatModel
        model = OpenAIChatModel(
            model_config.name,
            provider=model_config.provider,
        )
        
        # Use Union type: output is either a string (clarification question) or ExecutionPlan
        # NOTE: Removed history_processors to fix infinite loop issue.
        # The filter was removing tool calls/results from the CURRENT run, preventing the LLM
        # from seeing that it already called get_schema_summary, causing infinite loops.
        # The LLM needs to see its own tool calls within a single run to avoid repeating them.
        self.agent = Agent(
            model,
            instructions=prompt_template,
            output_type=Union[str, ExecutionPlan],
            deps_type=PlannerDeps,
            name="planner-agent"
        )
        
        # Register schema summary tool
        @self.agent.tool
        def get_schema_summary(ctx: RunContext[PlannerDeps]) -> str:
            """
            Get a lightweight summary of available database tables.
            
            Use this to quickly understand what data is available in the database.
            Returns database name, description, and a list of tables with their descriptions.
            This helps determine if the user's query can be answered with the available data.
            
            Returns:
                Summary string with database name, description, and table list with descriptions
            """
            # Check for cancellation before executing tool
            if ctx.deps.cancellation_event and ctx.deps.cancellation_event.is_set():
                logger.info("Tool call cancelled: PlannerAgent.get_schema_summary")
                raise RuntimeError("Request cancelled by user")
            
            logger.info("Tool call: PlannerAgent.get_schema_summary")
            if ctx.deps.schema_tool is None:
                return "Schema tool not available. Cannot get schema summary."
            
            # Check again after tool execution starts
            if ctx.deps.cancellation_event and ctx.deps.cancellation_event.is_set():
                logger.info("Tool execution cancelled: PlannerAgent.get_schema_summary")
                raise RuntimeError("Request cancelled by user")
            
            return ctx.deps.schema_tool.get_schema_summary()
    
    async def run(
        self, 
        user_message: str, 
        message_history: Optional[List[ModelMessage]] = None,
        cancellation_event: Optional[asyncio.Event] = None
    ):
        """
        Run the planner agent to create an execution plan or clarification question.
        
        Args:
            user_message: The user's message to plan for
            message_history: Optional message history for conversation context
            cancellation_event: Optional cancellation event to check
            
        Returns:
            Agent result with Union[str, ExecutionPlan] output:
            - str: Clarification question when more information is needed
            - ExecutionPlan: Complete execution plan when enough information is available
        """
        # Check for cancellation before starting
        if cancellation_event and cancellation_event.is_set():
            raise asyncio.CancelledError("Request cancelled by user")
        
        logger.info("LLM Call: PlannerAgent - creating execution plan")
        deps = PlannerDeps(schema_tool=self.schema_tool, cancellation_event=cancellation_event)
        
        try:
            if message_history:
                return await self.agent.run(user_message, deps=deps, message_history=message_history)
            else:
                return await self.agent.run(user_message, deps=deps)
        except (asyncio.CancelledError, RuntimeError) as e:
            if isinstance(e, RuntimeError) and "cancelled" in str(e).lower():
                logger.info("PlannerAgent cancelled")
                raise asyncio.CancelledError("Request cancelled by user")
            raise
