"""Session state management for orchestrator."""
from typing import Dict, Any, Optional, List
from pydantic_ai import ModelMessage
import logging

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages session state for the orchestrator."""
    
    def __init__(self):
        """Initialize session manager with empty state storage."""
        # Session state storage: {session_id: {"message_history": [...], "pending_clarification": {...}}}
        self._session_state: Dict[str, Dict[str, Any]] = {}
    
    def get_or_create_session(
        self, 
        session_id: str, 
        message_history: Optional[List[ModelMessage]] = None
    ) -> Dict[str, Any]:
        """
        Get or create a session state.
        
        Args:
            session_id: Session identifier
            message_history: Optional message history from database
            
        Returns:
            Session state dictionary
        """
        if session_id not in self._session_state:
            # New session - initialize with message history from database
            self._session_state[session_id] = {
                "message_history": message_history or [],
                "pending_clarification": None
            }
        else:
            # Existing session - merge database history with session state
            # Session state takes precedence (has most recent messages)
            # Only use database history if session state is empty
            if not self._session_state[session_id]["message_history"] and message_history:
                self._session_state[session_id]["message_history"] = message_history
        
        return self._session_state[session_id]
    
    def get_session_state(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get session state by ID.
        
        Args:
            session_id: Session identifier
            
        Returns:
            Session state dictionary or None if not found
        """
        return self._session_state.get(session_id)
    
    def reset_session(self, session_id: str) -> None:
        """
        Reset a specific session.
        
        Args:
            session_id: Session identifier to reset
        """
        if session_id in self._session_state:
            del self._session_state[session_id]
    
    def reset_all_sessions(self) -> None:
        """Reset all sessions."""
        self._session_state.clear()

