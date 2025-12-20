"""Message history management for orchestrator."""
from typing import List
from pydantic_ai import ModelMessage, ModelRequest, ModelResponse, UserPromptPart, TextPart, SystemPromptPart, Agent
import logging

logger = logging.getLogger(__name__)


class MessageHistoryManager:
    """Manages message history summarization and updates."""
    
    # Thresholds for message history management
    MAX_MESSAGES = 20
    KEEP_RECENT = 10
    
    def __init__(self, summarizer_agent: Agent):
        """
        Initialize message history manager.
        
        Args:
            summarizer_agent: Agent to use for summarization
        """
        self.summarizer_agent = summarizer_agent
    
    async def summarize_if_needed(self, messages: List[ModelMessage]) -> List[ModelMessage]:
        """
        Summarize message history when it grows too large.
        
        Args:
            messages: Current message history
            
        Returns:
            Summarized message history with recent messages preserved
        """
        if len(messages) <= self.MAX_MESSAGES:
            return messages
        
        # Split into old and recent messages
        old_messages = messages[:-self.KEEP_RECENT]
        recent_messages = messages[-self.KEEP_RECENT:]
        
        # Summarize old messages
        try:
            # Convert old messages to text for summarization
            old_messages_text = []
            for msg in old_messages:
                if isinstance(msg, ModelRequest):
                    for part in msg.parts:
                        if isinstance(part, UserPromptPart):
                            old_messages_text.append(f"User: {part.content}")
                elif isinstance(msg, ModelResponse):
                    for part in msg.parts:
                        if isinstance(part, TextPart):
                            old_messages_text.append(f"Assistant: {part.content}")
            
            summary_prompt = "Summarize this conversation history, focusing on key points and decisions:\n\n" + "\n".join(old_messages_text)
            
            summary_result = await self.summarizer_agent.run(summary_prompt)
            summary_text = summary_result.output if isinstance(summary_result.output, str) else str(summary_result.output)
            
            # Create a summary message
            summary_msg = ModelRequest(parts=[SystemPromptPart(content=f"[Previous conversation summary]: {summary_text}")])
            
            # Return summary + recent messages
            return [summary_msg] + recent_messages
        except Exception as e:
            logger.warning(f"Failed to summarize message history: {e}. Returning original messages.")
            return messages
    
    def add_message_to_history(
        self, 
        session_state: dict, 
        user_message: ModelMessage = None, 
        assistant_message: ModelMessage = None
    ) -> None:
        """
        Add messages to session history.
        
        Args:
            session_state: Session state dictionary
            user_message: Optional user message to add
            assistant_message: Optional assistant message to add
        """
        try:
            if user_message:
                session_state["message_history"].append(user_message)
            if assistant_message:
                session_state["message_history"].append(assistant_message)
        except Exception as e:
            logger.debug(f"Failed to update message history: {e}")

