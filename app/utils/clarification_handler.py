"""Clarification handling utilities for managing clarification flow."""
from typing import Dict, Any
from pydantic_ai import ModelRequest, ModelResponse, UserPromptPart, TextPart

from app.core.models import UserMessage, AgentResponse, IntentClassification
from app.utils.message_history import MessageHistoryManager


class ClarificationHandler:
    """Handles clarification requests by adding messages to history."""
    
    def __init__(self, message_history_manager: MessageHistoryManager):
        """
        Initialize clarification handler.
        
        Args:
            message_history_manager: Message history manager instance
        """
        self.message_history_manager = message_history_manager
    
    def handle_clarification_request(
        self,
        user_input: UserMessage,
        intent: IntentClassification,
        session_id: str,
        session_state: Dict[str, Any]
    ) -> AgentResponse:
        """
        Handle a clarification request - add messages to history and return clarification question.
        
        Args:
            user_input: Original user message
            intent: Intent classification result
            session_id: Session identifier
            session_state: Current session state
            
        Returns:
            AgentResponse with clarification question
        """
        clarification_message = intent.clarification_question or "Could you please clarify your question?"
        
        # Update message history with user message and clarification response
        # This allows the conversation to flow naturally - on the next turn,
        # the planner will see the full conversation including this clarification Q&A
        user_msg = ModelRequest(parts=[UserPromptPart(content=user_input.content)])
        assistant_msg = ModelResponse(parts=[TextPart(content=clarification_message)])
        self.message_history_manager.add_message_to_history(session_state, user_msg, assistant_msg)
        
        response = AgentResponse(
            message=clarification_message,
            requires_followup=True,
            metadata={
                "intent_type": intent.intent_type,
                "requires_clarification": True,
                "session_id": session_id
            }
        )
        
        return response

