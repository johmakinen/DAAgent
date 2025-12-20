"""Multi-agent orchestrator coordinating the agent pipeline."""
from pathlib import Path
from typing import Optional, List, Any
import mlflow
import logging
from pydantic_ai import ModelMessage, UserPromptPart, TextPart, ModelRequest, ModelResponse, Agent

from app.core.models import UserMessage, AgentResponse, IntentClassification, QueryAgentOutput
from app.core.config import Config
from app.core.prompt_registry import PromptRegistry
from app.core.pack_loader import DatabasePackLoader
from app.core.models import DatabasePack
from app.tools.db_tool import DatabaseTool
from app.agents.intent_agent import IntentAgent
from app.agents.database_query_agent import DatabaseQueryAgent
from app.agents.synthesizer_agent import SynthesizerAgent
from app.utils.session_manager import SessionManager
from app.utils.message_history import MessageHistoryManager
from app.utils.routing import Router
from app.utils.clarification_handler import ClarificationHandler
from app.utils.response_formatter import ResponseFormatter
from app.utils.tracing import TraceManager

logger = logging.getLogger(__name__)


class OrchestratorAgent:
    """
    Multi-agent orchestrator implementing the following flow:
    1. IntentAgent: Classifies user intent and determines if clarification is needed
    2. Router: Routes general questions directly to SynthesizerAgent, or database questions to DatabaseQueryAgent
    3. DatabaseQueryAgent: Generates SQL query and executes it (if database route)
    4. SynthesizerAgent: Takes agent output (or user question for general questions) and creates final user-facing response
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
            pack_path = Path(__file__).parent.parent / "packs" / "iris_database.yaml"
            if pack_path.exists():
                database_pack = DatabasePackLoader.load_pack(str(pack_path))
                logger.info(f"Loaded database pack: {database_pack.name}")
            else:
                logger.warning(f"Database pack not found at {pack_path}. Continuing without pack.")
        except Exception as e:
            logger.warning(f"Failed to load database pack: {e}. Continuing without pack.")
        
        # Initialize prompt registry
        self.prompt_registry = PromptRegistry()
        self.prompt_registry.initialize_all_prompts(force_update=True)
        
        # Load prompts from MLflow (or use fallback) with pack injection
        intent_prompt = self.prompt_registry.get_prompt_template("intent-agent", database_pack)
        database_query_prompt = self.prompt_registry.get_prompt_template("database-query-agent", database_pack)
        synthesizer_prompt = self.prompt_registry.get_prompt_template("synthesizer-agent", database_pack)
        
        # Initialize agents
        self.intent_agent = IntentAgent(model, intent_prompt, database_pack)
        self.database_query_agent = DatabaseQueryAgent(model, database_query_prompt, self.db_tool, database_pack)
        self.synthesizer_agent = SynthesizerAgent(model, synthesizer_prompt)
        
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
    
    @mlflow.trace(name="classify_intent")
    async def _classify_intent(
        self, 
        user_message: str, 
        message_history: Optional[List[ModelMessage]] = None
    ) -> tuple[IntentClassification, Any]:
        """
        Classify user intent and determine if clarification is needed.
        
        Args:
            user_message: The user's message
            message_history: Optional message history for context
        
        Returns:
            Tuple of (IntentClassification, RunResult) with intent type and clarification status
        """
        result = await self.intent_agent.run(user_message, message_history=message_history)
        return result.output, result
    
    @mlflow.trace(name="synthesize_response")
    async def _synthesize_response(
        self, 
        user_message: str,
        agent_output: Optional[QueryAgentOutput],
        intent_type: str,
        message_history: Optional[List[ModelMessage]] = None
    ) -> tuple[AgentResponse, Any]:
        """
        Synthesize final response from agent output or user question.
        
        Args:
            user_message: Original user question
            agent_output: Output from database query agent (None for general questions)
            intent_type: Type of intent that was processed
            message_history: Optional message history for context
        
        Returns:
            Tuple of (AgentResponse, RunResult) with final user-facing message
        """
        context = self.response_formatter.format_context_for_synthesizer(
            user_message, agent_output, intent_type
        )
        result = await self.synthesizer_agent.run(context, message_history=message_history)
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
        2. IntentAgent classifies intent and checks if clarification needed
        3. If clarification needed, store state and return clarification question
        4. Router directs general questions to SynthesizerAgent, or database questions to DatabaseQueryAgent
        5. SynthesizerAgent creates final user-facing response
        
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
            user_message_content, intent = self.clarification_handler.handle_clarification_response(
                user_input, session_state
            )
            self.trace_manager.tag_intent_type(intent.intent_type)
        else:
            # Normal flow - classify intent
            intent, intent_result = await self._classify_intent(
                user_input.content, 
                message_history=current_message_history
            )
            user_message_content = user_input.content
            self.trace_manager.tag_intent_type(intent.intent_type)
        
        # Check if clarification is needed
        if intent.requires_clarification:
            return self.clarification_handler.handle_clarification_request(
                user_input, intent, session_id, session_state
            )
        
        # Route to appropriate agent based on intent
        agent_output = None
        if intent.intent_type == "database_query":
            agent_output, _ = await self.router.route_to_database_query(
                user_message_content,
                message_history=current_message_history
            )
        
        # Synthesize final response
        response, _ = await self._synthesize_response(
            user_message_content,
            agent_output,
            intent.intent_type,
            message_history=current_message_history
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
        response.metadata["intent_type"] = intent.intent_type
        response.metadata["requires_database"] = (intent.intent_type == "database_query")
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
