"""Multi-agent orchestrator coordinating the agent pipeline."""
from pathlib import Path
from typing import Optional, List, Any
import mlflow
import logging
from pydantic_ai import ModelMessage, UserPromptPart, TextPart, ModelRequest, ModelResponse, Agent

from app.core.models import UserMessage, AgentResponse, IntentClassification, QueryAgentOutput, ExecutionPlan, DatabaseQuery
from app.core.config import Config
from app.core.prompt_registry import PromptRegistry
from app.core.pack_loader import DatabasePackLoader
from app.core.models import DatabasePack
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


class OrchestratorAgent:
    """
    Multi-agent orchestrator implementing the following flow:
    1. PlannerAgent: Creates execution plan with intent, plot requirements, and data source decisions
    2. Plan Execution: Uses cached data if specified, or executes DatabaseQueryAgent for new queries
    3. DatabaseQueryAgent: Generates SQL query and executes it (if new query needed)
    4. SynthesizerAgent: Takes agent output (or user question for general questions) and creates final user-facing response with plots if needed
    """
    
    def __init__(
        self,
        model: str = None,
        instructions: str = 'Be helpful and concise.'
    ):
        """
        Initialize all agents in the orchestration pipeline.
        
        Args:
            model: The model identifier for all agents (defaults to Config.DEFAULT_MODEL)
            instructions: Base system instructions (currently unused, kept for compatibility)
        """
        if model is None:
            model = Config.DEFAULT_MODEL
        
        self.db_tool = DatabaseTool()
        
        # Load database pack
        database_pack: Optional[DatabasePack] = None
        try:
            pack_path = Path(__file__).parent.parent / "packs" / "database_pack.yaml"
            if pack_path.exists():
                database_pack = DatabasePackLoader.load_pack(str(pack_path))
                logger.info(f"Loaded database pack: {database_pack.name}")
            else:
                logger.warning(f"Database pack not found at {pack_path}. Continuing without pack.")
        except Exception as e:
            logger.warning(f"Failed to load database pack: {e}. Continuing without pack.")
        
        # Initialize prompt registry
        self.prompt_registry = PromptRegistry()
        
        # Load prompts from MLflow (or use fallback) with pack injection
        planner_prompt = self.prompt_registry.get_prompt_template("planner-agent", database_pack)
        database_query_prompt = self.prompt_registry.get_prompt_template("database-query-agent", database_pack)
        synthesizer_prompt = self.prompt_registry.get_prompt_template("synthesizer-agent", database_pack)
        plot_planning_prompt = self.prompt_registry.get_prompt_template("plot-planning-agent", database_pack)
        
        # Initialize plot planning agent
        plot_planning_agent = PlotPlanningAgent(model, plot_planning_prompt, database_pack)
        
        # Initialize plot generator with plot planning agent
        self.plot_generator = PlotGenerator(plot_planning_agent=plot_planning_agent)
        
        # Initialize agents
        self.planner_agent = PlannerAgent(model, planner_prompt, database_pack)
        self.database_query_agent = DatabaseQueryAgent(model, database_query_prompt, self.db_tool, database_pack)
        self.synthesizer_agent = SynthesizerAgent(model, synthesizer_prompt, plot_generator=self.plot_generator)
        
        # Summarizer agent for message history management
        summarizer_agent = Agent(
            Config.SUMMARIZER_MODEL,
            instructions="Summarize this conversation, omitting small talk and unrelated topics. Focus on the technical discussion and next steps."
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
        message_history: Optional[List[ModelMessage]] = None
    ) -> tuple[ExecutionPlan, Any]:
        """
        Create an execution plan for the user's message.
        
        Args:
            user_message: The user's message
            message_history: Optional message history for context
        
        Returns:
            Tuple of (ExecutionPlan, RunResult) with execution plan
        """
        result = await self.planner_agent.run(user_message, message_history=message_history)
        return result.output, result
    
    @mlflow.trace(name="synthesize_response")
    async def _synthesize_response(
        self, 
        user_message: str,
        agent_output: Optional[QueryAgentOutput],
        intent_type: str,
        message_history: Optional[List[ModelMessage]] = None,
        execution_plan: Optional[ExecutionPlan] = None
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
            needs_data = (intent_type == "database_query" or 
                         (intent_type == "general_question" and 
                          execution_plan and execution_plan.requires_plot))
            if needs_data:
                if (agent_output.query_result.success and 
                    agent_output.query_result.data is not None and 
                    len(agent_output.query_result.data) > 0):
                    database_data = agent_output.query_result.data
        
        result = await self.synthesizer_agent.run(
            context, 
            message_history=message_history,
            database_data=database_data,
            user_question=user_message
        )
        return result.output, result
    
    @mlflow.trace(name="chat")
    async def chat(
        self, 
        user_input: UserMessage, 
        message_history: Optional[List[ModelMessage]] = None
    ) -> AgentResponse:
        """
        Main chat interface implementing the full orchestration flow.
        
        Flow:
        1. Check for pending clarification and handle accordingly
        2. PlannerAgent creates execution plan with intent, plot requirements, and data source decisions
        3. If clarification needed, store state and return clarification question
        4. Execute plan: use cached data if specified, or execute DatabaseQueryAgent for new queries
        5. Store new query results in session cache
        6. SynthesizerAgent creates final user-facing response with plots if needed
        
        Args:
            user_input: The user's message as a UserMessage model
            message_history: Optional message history for conversation context
            
        Returns:
            The agent's response as an AgentResponse model
        """
        # Get or create session state
        session_id = user_input.session_id or "default"
        session_state = self.session_manager.get_or_create_session(session_id, message_history)
        current_message_history = session_state["message_history"]
        
        # Summarize message history if it's too large
        current_message_history = await self.message_history_manager.summarize_if_needed(current_message_history)
        session_state["message_history"] = current_message_history
        
        # Tag MLflow trace with metadata
        self.trace_manager.tag_trace(
            session_id=session_id,
            username=user_input.username
        )
        
        # Handle clarification flow
        is_clarification_response = self.clarification_handler.is_clarification_response(session_state)
        
        if is_clarification_response:
            # User is responding to clarification
            user_message_content, intent_classification = self.clarification_handler.handle_clarification_response(
                user_input, session_state
            )
            # Convert IntentClassification to ExecutionPlan for consistency
            plan = ExecutionPlan(
                intent_type=intent_classification.intent_type,
                requires_clarification=intent_classification.requires_clarification,
                clarification_question=intent_classification.clarification_question,
                reasoning=intent_classification.reasoning,
                requires_plot=False,
                use_cached_data=False,
                explanation="Clarification response"
            )
            self.trace_manager.tag_intent_type(plan.intent_type)
        else:
            # Normal flow - create execution plan
            plan, plan_result = await self._create_plan(
                user_input.content, 
                message_history=current_message_history
            )
            user_message_content = user_input.content
            self.trace_manager.tag_intent_type(plan.intent_type)
        
        # Check if clarification is needed
        if plan.requires_clarification:
            # Convert ExecutionPlan to IntentClassification for compatibility with clarification handler
            intent_classification = IntentClassification(
                intent_type=plan.intent_type,
                requires_clarification=plan.requires_clarification,
                clarification_question=plan.clarification_question,
                reasoning=plan.reasoning
            )
            return self.clarification_handler.handle_clarification_request(
                user_input, intent_classification, session_id, session_state
            )
        
        # Execute plan: get data (cached or new query)
        # For database_query intents, always get data
        # For general_question intents, get data if plot is required
        agent_output = None
        needs_data = (plan.intent_type == "database_query" or 
                     (plan.intent_type == "general_question" and plan.requires_plot))
        
        if needs_data:
            if plan.use_cached_data:
                # Retrieve cached data
                if plan.cached_data_key:
                    agent_output = self.session_manager.get_query_result(session_id, plan.cached_data_key)
                else:
                    # Default to latest if no key specified
                    agent_output = self.session_manager.get_latest_query_result(session_id)
                
                if agent_output is None:
                    logger.warning(f"No cached data found for session {session_id}, falling back to new query")
                    # Fall back to new query if cached data not found
                    plan.use_cached_data = False
            
            if not plan.use_cached_data:
                # Execute new database query
                if plan.sql_query:
                    # Use SQL from plan if provided
                    db_query = DatabaseQuery(query=plan.sql_query)
                    query_result = self.db_tool.execute_query(db_query)
                    agent_output = QueryAgentOutput(
                        sql_query=plan.sql_query,
                        query_result=query_result,
                        explanation=plan.explanation
                    )
                else:
                    # Let DatabaseQueryAgent generate and execute query
                    agent_output, _ = await self.router.route_to_database_query(
                        user_message_content,
                        message_history=current_message_history
                    )
                
                # Store query result in cache
                if agent_output and agent_output.query_result.success:
                    import hashlib
                    import time
                    # Create a key from query hash and timestamp
                    query_hash = hashlib.md5(agent_output.sql_query.encode()).hexdigest()[:8]
                    timestamp = str(int(time.time()))
                    cache_key = f"{query_hash}_{timestamp}"
                    self.session_manager.store_query_result(session_id, cache_key, agent_output)
                    # Also store as 'latest' for easy access
                    self.session_manager.store_query_result(session_id, "latest", agent_output)
                    # Clear old results (keep last 5)
                    self.session_manager.clear_old_results(session_id, keep_last_n=5)
        
        # Synthesize final response (use plan's plot requirements if available)
        response, _ = await self._synthesize_response(
            user_message_content,
            agent_output,
            plan.intent_type,
            message_history=current_message_history,
            execution_plan=plan
        )
        
        # Update message history
        user_msg = None if is_clarification_response else ModelRequest(
            parts=[UserPromptPart(content=user_input.content)]
        )
        assistant_msg = ModelResponse(parts=[TextPart(content=response.message)])
        self.message_history_manager.add_message_to_history(session_state, user_msg, assistant_msg)
        
        # Add metadata
        if response.metadata is None:
            response.metadata = {}
        response.metadata["intent_type"] = plan.intent_type
        response.metadata["requires_database"] = (plan.intent_type == "database_query")
        response.metadata["session_id"] = session_id
        
        return response
    
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
