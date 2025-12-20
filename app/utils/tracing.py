"""MLflow tracing utilities for consistent trace tagging."""
from datetime import datetime
from typing import Optional, Dict, Any
import mlflow
import logging

logger = logging.getLogger(__name__)


class TraceManager:
    """Manages MLflow trace tagging and metadata."""
    
    @staticmethod
    def tag_trace(
        session_id: str,
        username: Optional[str] = None,
        intent_type: Optional[str] = None,
        **additional_tags: Any
    ) -> None:
        """
        Tag the current MLflow trace with metadata.
        
        Args:
            session_id: Session identifier
            username: Optional username for tracing
            intent_type: Optional intent type
            **additional_tags: Additional tags to add
        """
        try:
            tags: Dict[str, Any] = {
                "mlflow.trace.session": session_id,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            if username:
                tags["username"] = username
            
            if intent_type:
                tags["intent_type"] = intent_type
            
            # Add any additional tags
            tags.update(additional_tags)
            
            mlflow.update_current_trace(tags=tags)
        except Exception as e:
            logger.debug(f"Failed to tag MLflow trace: {e}")
    
    @staticmethod
    def tag_intent_type(intent_type: str) -> None:
        """
        Tag trace with intent type.
        
        Args:
            intent_type: Intent type to tag
        """
        try:
            mlflow.update_current_trace(tags={"intent_type": intent_type})
        except Exception as e:
            logger.debug(f"Failed to tag MLflow trace with intent_type: {e}")

