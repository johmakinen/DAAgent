from dotenv import load_dotenv
from typing import Literal
import mlflow

from app.core.models import (
    UserMessage, 
    AgentResponse, 
    IntentClassification,
    QueryAgentOutput,
    GeneralAnswerOutput
)
from app.core.prompt_registry import PromptRegistry
from app.tools.db_tool import DatabaseTool
from app.agents.intent_agent import IntentAgent
from app.agents.general_answer_agent import GeneralAnswerAgent
from app.agents.database_query_agent import DatabaseQueryAgent
from app.agents.synthesizer_agent import SynthesizerAgent

load_dotenv()


class OrchestratorAgent:
    """
    Multi-agent orchestrator implementing the following flow:
    1. IntentAgent: Classifies user intent and determines if clarification is needed
    2. Router: Routes to either GeneralAnswerAgent or DatabaseQueryAgent
    3. DatabaseQueryAgent: Generates SQL query and executes it (if database route)
    4. SynthesizerAgent: Takes agent output and creates final user-facing response
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
        
        # Initialize prompt registry
        self.prompt_registry = PromptRegistry()
        
        # Register all prompts if missing (using current templates as initial versions)
        self.prompt_registry.initialize_all_prompts()
        
        # Load prompts from MLflow (or use fallback)
        intent_prompt = self.prompt_registry.get_prompt_template("intent-agent")
        general_answer_prompt = self.prompt_registry.get_prompt_template("general-answer-agent")
        database_query_prompt = self.prompt_registry.get_prompt_template("database-query-agent")
        synthesizer_prompt = self.prompt_registry.get_prompt_template("synthesizer-agent")
        
        # Step 1: Intent Agent - Classifies intent and determines if clarification needed
        self.intent_agent = IntentAgent(model, intent_prompt)
        
        # Step 2a: General Answer Agent - Handles non-database questions
        self.general_answer_agent = GeneralAnswerAgent(model, general_answer_prompt)
        
        # Step 2b: Database Query Agent - Generates SQL and executes queries
        self.database_query_agent = DatabaseQueryAgent(model, database_query_prompt, self.db_tool)
        
        # Step 3: Synthesizer Agent - Creates final user-facing response
        self.synthesizer_agent = SynthesizerAgent(model, synthesizer_prompt)
    
    @mlflow.trace(name="classify_intent")
    async def _classify_intent(self, user_message: str) -> IntentClassification:
        """
        Step 1: Classify user intent and determine if clarification is needed.
        
        Returns:
            IntentClassification with intent type and clarification status
        """
        result = await self.intent_agent.run(user_message)
        return result.output
    
    @mlflow.trace(name="route_to_general_answer")
    async def _route_to_general_answer(self, user_message: str) -> GeneralAnswerOutput:
        """
        Step 2a: Route to general answer agent for non-database questions.
        
        Returns:
            GeneralAnswerOutput with the answer
        """
        result = await self.general_answer_agent.run(user_message)
        return result.output
    
    @mlflow.trace(name="route_to_database_query")
    async def _route_to_database_query(self, user_message: str) -> QueryAgentOutput:
        """
        Step 2b: Route to database query agent to generate and execute SQL.
        
        Returns:
            QueryAgentOutput with SQL query and results
        """
        result = await self.database_query_agent.run(user_message)
        return result.output
    
    @mlflow.trace(name="synthesize_response")
    async def _synthesize_response(
        self, 
        user_message: str,
        agent_output: GeneralAnswerOutput | QueryAgentOutput,
        intent_type: Literal["database_query", "general_question"]
    ) -> AgentResponse:
        """
        Step 3: Synthesize final response from agent output.
        
        Args:
            user_message: Original user question
            agent_output: Output from either general answer or database query agent
            intent_type: Type of intent that was processed
        
        Returns:
            AgentResponse with final user-facing message
        """
        # Format agent output for synthesizer
        if intent_type == "database_query":
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
            general_output: GeneralAnswerOutput = agent_output
            context = (
                f"User question: {user_message}\n\n"
                f"Answer: {general_output.answer}"
            )
        
        result = await self.synthesizer_agent.run(context)
        return result.output
    
    @mlflow.trace(name="chat")
    async def chat(self, user_input: UserMessage) -> AgentResponse:
        """
        Main chat interface implementing the full orchestration flow.
        
        Flow:
        1. IntentAgent classifies intent and checks if clarification needed
        2. If clarification needed, return response asking for clarification
        3. Router directs to either GeneralAnswerAgent or DatabaseQueryAgent
        4. SynthesizerAgent creates final user-facing response
        
        Args:
            user_input: The user's message as a UserMessage model
            
        Returns:
            The agent's response as an AgentResponse model
        """
        # Step 1: Classify intent
        intent: IntentClassification = await self._classify_intent(user_input.content)
        
        # Step 2: Check if clarification is needed
        if intent.requires_clarification:
            return AgentResponse(
                message=intent.clarification_question or "Could you please clarify your question?",
                requires_followup=True,
                metadata={"intent_type": intent.intent_type, "requires_clarification": True}
            )
        
        # Step 3: Route to appropriate agent based on intent
        if intent.intent_type == "database_query":
            agent_output = await self._route_to_database_query(user_input.content)
        else:
            agent_output = await self._route_to_general_answer(user_input.content)
        
        # Step 4: Synthesize final response
        response = await self._synthesize_response(
            user_input.content,
            agent_output,
            intent.intent_type
        )
        
        # Add metadata
        if response.metadata is None:
            response.metadata = {}
        response.metadata["intent_type"] = intent.intent_type
        response.metadata["requires_database"] = (intent.intent_type == "database_query")
        
        return response
    
    @mlflow.trace(name="reset")
    def reset(self) -> None:
        """Reset any conversation state (currently stateless, but kept for API compatibility)."""
        pass
