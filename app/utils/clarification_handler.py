"""Clarification handling utilities for managing clarification flow."""
from typing import Dict, Any, Optional, Tuple
from pydantic_ai import ModelMessage, ModelRequest, ModelResponse, UserPromptPart, TextPart

from app.core.models import UserMessage, AgentResponse, IntentClassification
from app.utils.message_history import MessageHistoryManager


class ClarificationHandler:
    """Handles clarification flow and state management."""
    
    def __init__(self, message_history_manager: MessageHistoryManager):
        """
        Initialize clarification handler.
        
        Args:
            message_history_manager: Message history manager instance
        """
        self.message_history_manager = message_history_manager
    
    def is_clarification_response(self, session_state: Dict[str, Any]) -> bool:
        """
        Check if the current message is a response to a clarification request.
        
        Args:
            session_state: Current session state
            
        Returns:
            True if this is a clarification response
        """
        return session_state.get("pending_clarification") is not None
    
    def handle_clarification_response(
        self,
        user_input: UserMessage,
        session_state: Dict[str, Any]
    ) -> Tuple[str, IntentClassification]:
        """
        Handle a user's response to a clarification request.
        
        Args:
            user_input: User's clarification response
            session_state: Current session state
            
        Returns:
            Tuple of (combined_message, stored_intent)
        """
        pending_clarification = session_state["pending_clarification"]
        original_message = pending_clarification["original_message"]
        stored_intent = pending_clarification["intent"]
        
        # Add user's clarification response to message history
        clarification_response_msg = ModelRequest(parts=[UserPromptPart(content=user_input.content)])
        self.message_history_manager.add_message_to_history(session_state, clarification_response_msg, None)
        
        # Combine messages for context - include original question in the message
        combined_message = f"{original_message}\n\n[Clarification response]: {user_input.content}"
        
        # Clear pending clarification
        session_state["pending_clarification"] = None
        
        return combined_message, stored_intent
    
    def handle_clarification_request(
        self,
        user_input: UserMessage,
        intent: IntentClassification,
        session_id: str,
        session_state: Dict[str, Any]
    ) -> AgentResponse:
        """
        Handle a clarification request - store state and return clarification question.
        
        Args:
            user_input: Original user message
            intent: Intent classification result
            session_id: Session identifier
            session_state: Current session state
            
        Returns:
            AgentResponse with clarification question
        """
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
            metadata={
                "intent_type": intent.intent_type,
                "requires_clarification": True,
                "session_id": session_id
            }
        )
        
        return response

