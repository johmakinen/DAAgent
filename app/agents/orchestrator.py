"""Multi-agent orchestrator coordinating the agent pipeline."""

from pathlib import Path
from typing import Optional, List, Any, Union
import mlflow
import logging
import hashlib
import time
import asyncio
from pydantic_ai import (
    ModelMessage,
    UserPromptPart,
    TextPart,
    ModelRequest,
    ModelResponse,
    Agent,
)
from pydantic_ai.models.openai import OpenAIChatModel

from app.core.models import (
    UserMessage,
    AgentResponse,
    IntentClassification,
    QueryAgentOutput,
    ExecutionPlan,
)
from app.core.config import Config
from app.core.prompt_registry import PromptRegistry
from app.core.pack_loader import DatabasePackLoader
from app.core.models import DatabasePack
from app.core.schema_skills import SchemaSkill
from app.tools.schema_tool import SchemaTool
from app.tools.db_tool import DatabaseTool
from app.agents.planner_agent import PlannerAgent
from app.agents.database_query_agent import DatabaseQueryAgent
from app.agents.synthesizer_agent import SynthesizerAgent
from app.agents.plot_planning_agent import PlotPlanningAgent
from app.utils.session_manager import SessionManager
from app.utils.message_history import MessageHistoryManager
from app.utils.routing import Router
from app.utils.clarification_handler import ClarificationHandler
from app.utils.response_formatter import ResponseFormatter
from app.utils.tracing import TraceManager
from app.utils.plot_generator import PlotGenerator

logger = logging.getLogger(__name__)

mlflow.pydantic_ai.autolog()


class OrchestratorAgent:
    """
    Multi-agent orchestrator implementing the following flow:
    1. PlannerAgent: Creates execution plan with intent, plot requirements, and data source decisions
    2. Plan Execution: Uses cached data if specified, or executes DatabaseQueryAgent for new queries
    3. DatabaseQueryAgent: Generates SQL query and executes it (if new query needed)
    4. SynthesizerAgent: Takes agent output (or user question for general questions) and creates final user-facing response with plots if needed
    """

    def __init__(self, instructions: str = "Be helpful and concise."):
        """
        Initialize all agents in the orchestration pipeline.

        Args:
            instructions: Base system instructions (currently unused, kept for compatibility)
        """
        self.db_tool = DatabaseTool()

        # Load database pack
        database_pack: Optional[DatabasePack] = None
        try:
            pack_path = Path(__file__).parent.parent / "packs" / "database_pack.yaml"
            if pack_path.exists():
                database_pack = DatabasePackLoader.load_pack(str(pack_path))
                logger.info(f"Loaded database pack: {database_pack.name}")
            else:
                logger.warning(
                    f"Database pack not found at {pack_path}. Continuing without pack."
                )
        except Exception as e:
            logger.warning(
                f"Failed to load database pack: {e}. Continuing without pack."
            )

        # Initialize schema skill system for progressive disclosure
        schema_skill = SchemaSkill(database_pack)
        schema_tool = SchemaTool(schema_skill)

        # Initialize prompt registry
        self.prompt_registry = PromptRegistry()

        # Load prompts from MLflow (or use fallback) with progressive disclosure
        # PlannerAgent: summary schema (table names only)
        planner_prompt = self.prompt_registry.get_prompt_template(
            "planner-agent", database_pack, schema_level="summary"
        )
        # DatabaseQueryAgent: no schema in prompt (loads via tools)
        database_query_prompt = self.prompt_registry.get_prompt_template(
            "database-query-agent", database_pack, schema_level="none"
        )
        # SynthesizerAgent: no schema needed
        synthesizer_prompt = self.prompt_registry.get_prompt_template(
            "synthesizer-agent", database_pack, schema_level="none"
        )
        # PlotPlanningAgent: no schema needed (uses query result columns)
        plot_planning_prompt = self.prompt_registry.get_prompt_template(
            "plot-planning-agent", database_pack, schema_level="none"
        )

        # Initialize plot planning agent
        plot_planning_agent = PlotPlanningAgent(
            plot_planning_prompt, database_pack
        )

        # Initialize plot generator with plot planning agent
        self.plot_generator = PlotGenerator(plot_planning_agent=plot_planning_agent)

        # Initialize agents with progressive disclosure
        self.planner_agent = PlannerAgent(
            planner_prompt, database_pack, schema_tool=schema_tool
        )
        self.database_query_agent = DatabaseQueryAgent(
            database_query_prompt,
            self.db_tool,
            schema_tool=schema_tool,
            database_pack=database_pack,
        )
        self.synthesizer_agent = SynthesizerAgent(
            synthesizer_prompt, plot_generator=self.plot_generator
        )

        # Summarizer agent for message history management
        # Get model configuration for summarizer
        summarizer_model_config = Config.get_model('summarizer')
        summarizer_model = OpenAIChatModel(
            summarizer_model_config.name,
            provider=summarizer_model_config.provider,
        )
        summarizer_agent = Agent(
            summarizer_model,
            instructions="Summarize this conversation, omitting small talk and unrelated topics. Focus on the technical discussion and next steps.",
        )

        # Initialize utilities
        self.session_manager = SessionManager()
        self.message_history_manager = MessageHistoryManager(summarizer_agent)
        self.router = Router(self.database_query_agent)
        self.clarification_handler = ClarificationHandler(self.message_history_manager)
        self.response_formatter = ResponseFormatter()
        self.trace_manager = TraceManager()

        # Set MLflow experiment if configured
        if Config.MLFLOW_EXPERIMENT_NAME:
            mlflow.set_experiment(Config.MLFLOW_EXPERIMENT_NAME)

    @mlflow.trace(name="create_plan")
    async def _create_plan(
        self, 
        user_message: str, 
        message_history: Optional[List[ModelMessage]] = None,
        cancellation_event: Optional[asyncio.Event] = None
    ) -> tuple[Union[str, ExecutionPlan], Any]:
        """
        Create an execution plan for the user's message.

        Args:
            user_message: The user's message
            message_history: Optional message history for context
            cancellation_event: Optional cancellation event to check

        Returns:
            Tuple of (Union[str, ExecutionPlan], RunResult):
            - str: Clarification question when more information is needed
            - ExecutionPlan: Complete execution plan when enough information is available
        """
        # Check for cancellation before running planner
        self._check_cancellation(cancellation_event)
        
        # Run planner agent with cancellation support
        # The planner agent and its tools will check cancellation internally
        try:
            result = await self.planner_agent.run(
                user_message, 
                message_history=message_history,
                cancellation_event=cancellation_event
            )
            # Check one more time after completion
            self._check_cancellation(cancellation_event)
            return result.output, result
        except asyncio.CancelledError:
            logger.info("Planner agent execution cancelled")
            raise

    @mlflow.trace(name="synthesize_response")
    async def _synthesize_response(
        self,
        user_message: str,
        agent_output: Optional[QueryAgentOutput],
        intent_type: str,
        message_history: Optional[List[ModelMessage]] = None,
        execution_plan: Optional[ExecutionPlan] = None,
    ) -> tuple[AgentResponse, Any]:
        """
        Synthesize final response from agent output or user question.

        Args:
            user_message: Original user question
            agent_output: Output from database query agent (None for general questions without plots,
                         or when no data is needed)
            intent_type: Type of intent that was processed
            message_history: Optional message history for context
            execution_plan: Optional execution plan with plot requirements

        Returns:
            Tuple of (AgentResponse, RunResult) with final user-facing message
        """
        context = self.response_formatter.format_context_for_synthesizer(
            user_message, agent_output, intent_type, execution_plan
        )

        # Extract database data for plot generation
        # For database_query: always extract if available
        # For general_question: extract if plot is required and data is available
        database_data = None
        if agent_output is not None:
            needs_data = intent_type == "database_query" or (
                intent_type == "general_question"
                and execution_plan
                and execution_plan.requires_plot
            )
            if needs_data:
                if (
                    agent_output.query_result.success
                    and agent_output.query_result.data is not None
                    and len(agent_output.query_result.data) > 0
                ):
                    database_data = agent_output.query_result.data

        result = await self.synthesizer_agent.run(
            context,
            message_history=message_history,
            database_data=database_data,
            user_question=user_message,
            execution_plan=execution_plan,
        )
        return result.output, result

    @mlflow.trace(name="prepare_session_and_history")
    async def _prepare_session_and_history(
        self,
        user_input: UserMessage,
        message_history: Optional[List[ModelMessage]] = None,
    ) -> tuple[str, dict[str, Any], List[ModelMessage]]:
        """
        Prepare session state, summarize history if needed, and tag trace.

        Args:
            user_input: The user's message as a UserMessage model
            message_history: Optional message history for conversation context

        Returns:
            Tuple of (session_id, session_state, current_message_history)
        """
        # Get or create session state
        session_id = user_input.session_id or "default"
        session_state = self.session_manager.get_or_create_session(
            session_id, message_history
        )
        current_message_history = session_state["message_history"]

        # Summarize message history if it's too large
        current_message_history = (
            await self.message_history_manager.summarize_if_needed(
                current_message_history
            )
        )
        session_state["message_history"] = current_message_history

        # Tag MLflow trace with metadata
        self.trace_manager.tag_trace(
            session_id=session_id, username=user_input.username
        )

        return session_id, session_state, current_message_history

    @mlflow.trace(name="create_plan")
    async def _create_plan_with_history(
        self,
        user_input: UserMessage,
        current_message_history: List[ModelMessage],
        cancellation_event: Optional[asyncio.Event] = None,
    ) -> tuple[Union[str, ExecutionPlan], Any]:
        """
        Create an execution plan for the user's message with full message history.

        Args:
            user_input: The user's message as a UserMessage model
            current_message_history: Current message history (includes user's message)

        Returns:
            Tuple of (Union[str, ExecutionPlan], RunResult):
            - str: Clarification question when more information is needed
            - ExecutionPlan: Complete execution plan when enough information is available
        """
        # Check for cancellation before planning
        self._check_cancellation(cancellation_event)
        
        # Create execution plan with full message history
        # The message history includes all previous messages, including any clarification Q&A
        plan_or_clarification, plan_result = await self._create_plan(
            user_input.content, 
            message_history=current_message_history,
            cancellation_event=cancellation_event
        )
        
        # Check for cancellation after planning
        self._check_cancellation(cancellation_event)
        
        # If it's an ExecutionPlan, tag the intent type
        if isinstance(plan_or_clarification, ExecutionPlan):
            self.trace_manager.tag_intent_type(plan_or_clarification.intent_type)
        
        return plan_or_clarification, plan_result

    @mlflow.trace(name="execute_plan")
    async def _execute_plan(
        self,
        plan: ExecutionPlan,
        user_message_content: str,
        session_id: str,
        current_message_history: List[ModelMessage],
        cancellation_event: Optional[asyncio.Event] = None,
    ) -> Optional[QueryAgentOutput]:
        """
        Execute the plan to get data (cached or new query).

        Args:
            plan: Execution plan with data requirements
            user_message_content: The user's message content
            session_id: Session identifier
            current_message_history: Current message history

        Returns:
            QueryAgentOutput with query results, or None if no data needed
        """
        # Check for cancellation before executing plan
        self._check_cancellation(cancellation_event)
        
        # Execute plan: get data (cached or new query)
        # For database_query intents, always get data
        # For general_question intents, get data if plot is required
        agent_output = None
        needs_data = plan.intent_type == "database_query" or (
            plan.intent_type == "general_question" and plan.requires_plot
        )

        if needs_data:
            if plan.use_cached_data:
                # Retrieve cached data
                if plan.cached_data_key:
                    agent_output = self.session_manager.get_query_result(
                        session_id, plan.cached_data_key
                    )
                else:
                    # Default to latest if no key specified
                    agent_output = self.session_manager.get_latest_query_result(
                        session_id
                    )

                if agent_output is None:
                    logger.warning(
                        f"No cached data found for session {session_id}, falling back to new query"
                    )
                    # Fall back to new query if cached data not found
                    plan.use_cached_data = False

            if not plan.use_cached_data:
                # Check for cancellation before executing query
                self._check_cancellation(cancellation_event)
                
                # Execute new database query
                # Always use DatabaseQueryAgent to generate and execute query
                agent_output, _ = await self.router.route_to_database_query(
                    user_message_content, message_history=current_message_history
                )
                
                # Check for cancellation after query execution
                self._check_cancellation(cancellation_event)

                # Store query result in cache
                if agent_output and agent_output.query_result.success:
                    # Create a key from query hash and timestamp
                    query_hash = hashlib.md5(
                        agent_output.sql_query.encode()
                    ).hexdigest()[:8]
                    timestamp = str(int(time.time()))
                    cache_key = f"{query_hash}_{timestamp}"
                    self.session_manager.store_query_result(
                        session_id, cache_key, agent_output
                    )
                    # Also store as 'latest' for easy access
                    self.session_manager.store_query_result(
                        session_id, "latest", agent_output
                    )
                    # Clear old results (keep last 5)
                    self.session_manager.clear_old_results(session_id, keep_last_n=5)

        return agent_output

    @mlflow.trace(name="finalize_response")
    async def _finalize_response(
        self,
        user_message_content: str,
        agent_output: Optional[QueryAgentOutput],
        plan: ExecutionPlan,
        session_id: str,
        session_state: dict[str, Any],
        current_message_history: List[ModelMessage],
        user_input: UserMessage,
    ) -> AgentResponse:
        """
        Synthesize response, update message history, and add metadata.

        Args:
            user_message_content: The user's message content
            agent_output: Output from database query agent (None if no data needed)
            plan: Execution plan
            session_id: Session identifier
            session_state: Current session state
            current_message_history: Current message history
            user_input: Original user input for history update

        Returns:
            AgentResponse with final response and metadata
        """
        # Synthesize final response (use plan's plot requirements if available)
        response, _ = await self._synthesize_response(
            user_message_content,
            agent_output,
            plan.intent_type,
            message_history=current_message_history,
            execution_plan=plan,
        )

        # Update message history - always add assistant response
        # Note: user message was already added to history before planner ran
        assistant_msg = ModelResponse(parts=[TextPart(content=response.message)])
        self.message_history_manager.add_message_to_history(
            session_state, None, assistant_msg
        )

        # Add metadata
        if response.metadata is None:
            response.metadata = {}
        response.metadata["intent_type"] = plan.intent_type
        response.metadata["requires_database"] = plan.intent_type == "database_query"
        response.metadata["session_id"] = session_id

        return response

    def _check_cancellation(self, cancellation_event: Optional[asyncio.Event] = None):
        """Check if cancellation was requested and raise CancelledError if so."""
        if cancellation_event and cancellation_event.is_set():
            raise asyncio.CancelledError("Request cancelled by user")

    @mlflow.trace(name="chat")
    async def chat(
        self,
        user_input: UserMessage,
        message_history: Optional[List[ModelMessage]] = None,
        cancellation_event: Optional[asyncio.Event] = None,
    ) -> AgentResponse:
        """
        Main chat interface implementing the full orchestration flow.

        Flow:
        1. Prepare session and message history
        2. Add user message to history (so planner sees full conversation context)
        3. PlannerAgent creates execution plan with intent, plot requirements, and data source decisions
        4. If clarification needed, add clarification response to history and return
        5. Execute plan: use cached data if specified, or execute DatabaseQueryAgent for new queries
        6. Store new query results in session cache
        7. SynthesizerAgent creates final user-facing response with plots if needed

        Args:
            user_input: The user's message as a UserMessage model
            message_history: Optional message history for conversation context
            cancellation_event: Optional asyncio.Event to check for cancellation requests

        Returns:
            The agent's response as an AgentResponse model
        """
        # Check for cancellation before starting
        self._check_cancellation(cancellation_event)
        
        # Prepare session
        session_id, session_state, current_message_history = (
            await self._prepare_session_and_history(user_input, message_history)
        )

        # Check for cancellation after session prep
        self._check_cancellation(cancellation_event)

        # Add user message to history BEFORE running planner
        # This ensures the planner sees the full conversation context, including
        # any previous clarification Q&A and the current user message
        user_msg = ModelRequest(parts=[UserPromptPart(content=user_input.content)])
        self.message_history_manager.add_message_to_history(
            session_state, user_msg, None
        )
        # Update current_message_history to include the user's message
        current_message_history = session_state["message_history"]

        # Create execution plan with full message history
        plan_or_clarification, _ = await self._create_plan_with_history(
            user_input, current_message_history, cancellation_event
        )
        
        # Check for cancellation after planning
        self._check_cancellation(cancellation_event)

        # Check if planner returned a clarification string
        if isinstance(plan_or_clarification, str):
            # Planner returned a clarification question as a string
            intent_classification = IntentClassification(
                intent_type="database_query",  # Default, will be re-evaluated after clarification
                requires_clarification=True,
                clarification_question=plan_or_clarification,
                reasoning="User question requires clarification before execution plan can be created.",
            )
            return self.clarification_handler.handle_clarification_request(
                user_input, intent_classification, session_id, session_state
            )

        # Planner returned an ExecutionPlan - proceed with execution
        plan = plan_or_clarification

        # Execute plan
        agent_output = await self._execute_plan(
            plan, user_input.content, session_id, current_message_history, cancellation_event
        )
        
        # Check for cancellation after plan execution
        self._check_cancellation(cancellation_event)

        # Check if DatabaseQueryAgent needs clarification
        if agent_output is not None and agent_output.requires_clarification:
            # Convert QueryAgentOutput clarification to IntentClassification for compatibility
            intent_classification = IntentClassification(
                intent_type=plan.intent_type,
                requires_clarification=True,
                clarification_question=agent_output.clarification_question or "Could you please clarify which column you meant?",
                reasoning=f"Database query failed after retries. {agent_output.explanation}"
            )
            return self.clarification_handler.handle_clarification_request(
                user_input, intent_classification, session_id, session_state
            )

        # Check for cancellation before finalizing
        self._check_cancellation(cancellation_event)
        
        # Finalize response
        return await self._finalize_response(
            user_input.content,
            agent_output,
            plan,
            session_id,
            session_state,
            current_message_history,
            user_input,
        )

    @mlflow.trace(name="reset")
    def reset(self, session_id: Optional[str] = None) -> None:
        """
        Reset conversation state for a session or all sessions.

        Args:
            session_id: Optional session ID to reset. If None, resets all sessions.
        """
        if session_id:
            self.session_manager.reset_session(session_id)
        else:
            self.session_manager.reset_all_sessions()
