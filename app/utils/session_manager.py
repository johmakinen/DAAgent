"""Session state management for orchestrator."""
from typing import Dict, Any, Optional, List
from pydantic_ai import ModelMessage
import logging
from app.core.models import QueryAgentOutput

logger = logging.getLogger(__name__)


class SessionManager:
    """Manages session state for the orchestrator."""
    
    def __init__(self):
        """Initialize session manager with empty state storage."""
        # Session state storage: {session_id: {"message_history": [...], "cached_query_results": {...}}}
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
                "cached_query_results": {}  # Dict[str, QueryAgentOutput] - keyed by query identifier
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
    
    def store_query_result(self, session_id: str, key: str, result: QueryAgentOutput) -> None:
        """
        Store a query result in session cache.
        
        Args:
            session_id: Session identifier
            key: Key to identify this query result (e.g., 'latest', query hash, or timestamp)
            result: QueryAgentOutput to store
        """
        session_state = self.get_or_create_session(session_id)
        if "cached_query_results" not in session_state:
            session_state["cached_query_results"] = {}
        session_state["cached_query_results"][key] = result
        logger.debug(f"Stored query result with key '{key}' for session {session_id}")
    
    def get_query_result(self, session_id: str, key: str) -> Optional[QueryAgentOutput]:
        """
        Get a cached query result by key.
        
        Args:
            session_id: Session identifier
            key: Key identifying the query result
        
        Returns:
            QueryAgentOutput if found, None otherwise
        """
        session_state = self.get_session_state(session_id)
        if not session_state:
            return None
        
        cached_results = session_state.get("cached_query_results", {})
        return cached_results.get(key)
    
    def get_latest_query_result(self, session_id: str) -> Optional[QueryAgentOutput]:
        """
        Get the most recently stored query result.
        
        Args:
            session_id: Session identifier
        
        Returns:
            Most recent QueryAgentOutput if any exist, None otherwise
        """
        session_state = self.get_session_state(session_id)
        if not session_state:
            return None
        
        cached_results = session_state.get("cached_query_results", {})
        if not cached_results:
            return None
        
        # Try 'latest' key first, otherwise get the last item
        if "latest" in cached_results:
            return cached_results["latest"]
        
        # Return the last item in the dict (Python 3.7+ maintains insertion order)
        if cached_results:
            return list(cached_results.values())[-1]
        
        return None
    
    def clear_old_results(self, session_id: str, keep_last_n: int = 5) -> None:
        """
        Clear old cached query results, keeping only the most recent N.
        
        Args:
            session_id: Session identifier
            keep_last_n: Number of recent results to keep (default: 5)
        """
        session_state = self.get_session_state(session_id)
        if not session_state:
            return
        
        cached_results = session_state.get("cached_query_results", {})
        if len(cached_results) <= keep_last_n:
            return
        
        # Keep 'latest' if it exists, then keep the most recent N-1 others
        latest = cached_results.pop("latest", None)
        
        # Convert to list of (key, value) tuples, sort by some criteria (we'll use insertion order)
        items = list(cached_results.items())
        
        # Keep only the last N-1 items (or N if no 'latest')
        keep_count = keep_last_n - (1 if latest else 0)
        items_to_keep = items[-keep_count:] if len(items) > keep_count else items
        
        # Rebuild the dict
        new_results = {}
        if latest:
            new_results["latest"] = latest
        for key, value in items_to_keep:
            new_results[key] = value
        
        session_state["cached_query_results"] = new_results
        logger.debug(f"Cleared old results for session {session_id}, kept {len(new_results)} results")

