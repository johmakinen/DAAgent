from dotenv import load_dotenv
from pathlib import Path
from typing import Literal, Dict, Any, Optional, List
from datetime import datetime
import mlflow
import logging
from pydantic_ai import ModelMessage, UserPromptPart, TextPart, ModelRequest, ModelResponse, Agent, SystemPromptPart

from app.core.models import (
    UserMessage, 
    AgentResponse, 
    IntentClassification,
    QueryAgentOutput,
)

logger = logging.getLogger(__name__)
from app.core.prompt_registry import PromptRegistry
from app.core.pack_loader import DatabasePackLoader
from app.core.models import DatabasePack
from app.tools.db_tool import DatabaseTool
from app.agents.intent_agent import IntentAgent
from app.agents.database_query_agent import DatabaseQueryAgent
from app.agents.synthesizer_agent import SynthesizerAgent
from app.agents.session_manager import SessionManager
from app.agents.message_history import MessageHistoryManager

load_dotenv()


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
        model: str = 'azure:gpt-5-nano',
        instructions: str = 'Be helpful and concise.'
    ):
        """
        Initialize all agents in the orchestration pipeline.
        
        Args:
            model: The model identifier for all agents
            instructions: Base system instructions (currently unused, kept for compatibility)
        """
        self.db_tool = DatabaseTool()
        
        # Load database pack
        database_pack: Optional[DatabasePack] = None
        try:
            # Try to load the iris database pack
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
        
        # Force update all prompts to ensure latest versions from codebase are used
        # This ensures all agents have the most up-to-date prompts, including any fixes
        self.prompt_registry.initialize_all_prompts(force_update=True)
        
        # Load prompts from MLflow (or use fallback) with pack injection
        intent_prompt = self.prompt_registry.get_prompt_template("intent-agent", database_pack)
        database_query_prompt = self.prompt_registry.get_prompt_template("database-query-agent", database_pack)
        synthesizer_prompt = self.prompt_registry.get_prompt_template("synthesizer-agent", database_pack)
        
        # Step 1: Intent Agent - Classifies intent and determines if clarification needed
        self.intent_agent = IntentAgent(model, intent_prompt, database_pack)
        
        # Step 2: Database Query Agent - Generates SQL and executes queries
        self.database_query_agent = DatabaseQueryAgent(model, database_query_prompt, self.db_tool, database_pack)
        
        # Step 3: Synthesizer Agent - Creates final user-facing response (handles both general questions and database results)
        self.synthesizer_agent = SynthesizerAgent(model, synthesizer_prompt)
        
        # Summarizer agent for message history management (use cheaper model)
        summarizer_agent = Agent(
            'azure:gpt-5-mini',
            instructions="Summarize this conversation, omitting small talk and unrelated topics. Focus on the technical discussion and next steps."
        )
        
        # Initialize session and message history managers
        self.session_manager = SessionManager()
        self.message_history_manager = MessageHistoryManager(summarizer_agent)
    
    @mlflow.trace(name="classify_intent")
    async def _classify_intent(self, user_message: str, message_history: Optional[List[ModelMessage]] = None) -> tuple[IntentClassification, Any]:
        """
        Step 1: Classify user intent and determine if clarification is needed.
        
        Args:
            user_message: The user's message
            message_history: Optional message history for context
        
        Returns:
            Tuple of (IntentClassification, RunResult) with intent type and clarification status
        """
        result = await self.intent_agent.run(user_message, message_history=message_history)
        return result.output, result
    
    @mlflow.trace(name="route_to_database_query")
    async def _route_to_database_query(self, user_message: str, message_history: Optional[List[ModelMessage]] = None) -> tuple[QueryAgentOutput, Any]:
        """
        Step 2b: Route to database query agent to generate and execute SQL.
        
        Args:
            user_message: The user's message
            message_history: Optional message history for context
        
        Returns:
            Tuple of (QueryAgentOutput, RunResult) with SQL query and results
        """
        result = await self.database_query_agent.run(user_message, message_history=message_history)
        return result.output, result
    
    @mlflow.trace(name="synthesize_response")
    async def _synthesize_response(
        self, 
        user_message: str,
        agent_output: Optional[QueryAgentOutput],
        intent_type: Literal["database_query", "general_question"],
        message_history: Optional[List[ModelMessage]] = None
    ) -> tuple[AgentResponse, Any]:
        """
        Step 3: Synthesize final response from agent output or user question.
        
        Args:
            user_message: Original user question
            agent_output: Output from database query agent (None for general questions)
            intent_type: Type of intent that was processed
        
        Returns:
            Tuple of (AgentResponse, RunResult) with final user-facing message
        """
        # Format context for synthesizer
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
        
        result = await self.synthesizer_agent.run(context, message_history=message_history)
        return result.output, result
    
    @mlflow.trace(name="chat")
    async def chat(self, user_input: UserMessage, message_history: Optional[List[ModelMessage]] = None) -> AgentResponse:
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
        
        # Tag MLflow trace with metadata (for admin/debugging)
        try:
            tags = {
                "mlflow.trace.session": session_id,
                "timestamp": datetime.utcnow().isoformat()
            }
            if user_input.username:
                tags["username"] = user_input.username
            mlflow.update_current_trace(tags=tags)
        except Exception as e:
            logger.debug(f"Failed to tag MLflow trace: {e}")
        
        # Handle pending clarification
        pending_clarification = session_state.get("pending_clarification")
        is_clarification_response = pending_clarification is not None
        
        intent_result = None
        if is_clarification_response:
            # User is responding to clarification
            original_message = pending_clarification["original_message"]
            stored_intent = pending_clarification["intent"]
            
            # Add user's clarification response to message history
            clarification_response_msg = ModelRequest(parts=[UserPromptPart(content=user_input.content)])
            self.message_history_manager.add_message_to_history(session_state, clarification_response_msg, None)
            
            # Combine messages for context - include original question in the message
            combined_message = f"{original_message}\n\n[Clarification response]: {user_input.content}"
            
            # Use stored intent instead of re-classifying
            intent = stored_intent
            
            # Add intent_type to MLflow trace
            try:
                mlflow.update_current_trace(tags={"intent_type": intent.intent_type})
            except Exception as e:
                logger.debug(f"Failed to tag MLflow trace with intent_type: {e}")
            
            # Clear pending clarification
            session_state["pending_clarification"] = None
            
            # Use combined message for processing
            user_message_content = combined_message
        else:
            # Normal flow - classify intent
            # Step 1: Classify intent
            intent, intent_result = await self._classify_intent(
                user_input.content, 
                message_history=current_message_history
            )
            user_message_content = user_input.content
            
            # Add intent_type to MLflow trace
            try:
                mlflow.update_current_trace(tags={"intent_type": intent.intent_type})
            except Exception as e:
                logger.debug(f"Failed to tag MLflow trace with intent_type: {e}")
        
        # Step 2: Check if clarification is needed
        if intent.requires_clarification:
            # Store original message and intent for when user responds
            session_state["pending_clarification"] = {
                "original_message": user_input.content,
                "intent": intent
            }
            
            clarification_message = intent.clarification_question or "Could you please clarify your question?"
            
            # Update message history with user message and clarification response
            user_msg = ModelRequest(parts=[UserPromptPart(content=user_input.content)])
            assistant_msg = ModelResponse(parts=[TextPart(content=clarification_message)])
            self.message_history_manager.add_message_to_history(session_state, user_msg, assistant_msg)
            
            response = AgentResponse(
                message=clarification_message,
                requires_followup=True,
                metadata={"intent_type": intent.intent_type, "requires_clarification": True, "session_id": session_id}
            )
            
            return response
        
        # Step 3: Route to appropriate agent based on intent
        agent_result = None
        agent_output = None
        if intent.intent_type == "database_query":
            agent_output, agent_result = await self._route_to_database_query(
                user_message_content,
                message_history=current_message_history
            )
        
        # Step 4: Synthesize final response
        # For general questions, agent_output is None and synthesizer handles the question directly
        # For database queries, agent_output contains the query results
        response, synthesizer_result = await self._synthesize_response(
            user_message_content,
            agent_output,
            intent.intent_type,
            message_history=current_message_history
        )
        
        # Update message history with this exchange
        # Note: For clarification responses, the user's clarification response is already in history
        # For normal flow, we need to add the user message
        user_msg = None
        if not is_clarification_response:
            # Normal flow - add user message
            user_msg = ModelRequest(parts=[UserPromptPart(content=user_input.content)])
        
        # Always add assistant response
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
