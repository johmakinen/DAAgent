"""API request and response models."""
from pydantic import BaseModel
from typing import Optional, Dict, Any, List


class LoginRequest(BaseModel):
    """Login request model."""
    username: str


class LoginResponse(BaseModel):
    """Login response model."""
    access_token: str
    token_type: str = "bearer"
    user_id: int
    username: str


class ChatRequest(BaseModel):
    """Chat request model."""
    message: str
    chat_session_id: int


class ChatResponse(BaseModel):
    """Chat response model."""
    response: str
    intent_type: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    plot_spec: Optional[Dict[str, Any]] = None


class ChatMessage(BaseModel):
    """Chat message model for history."""
    id: int
    message: str
    response: str
    intent_type: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    plot_spec: Optional[Dict[str, Any]] = None
    created_at: str


class ChatHistoryResponse(BaseModel):
    """Chat history response model."""
    messages: List[ChatMessage]
    chat_session_id: int


class ChatSession(BaseModel):
    """Chat session model."""
    id: int
    user_id: int
    title: Optional[str] = None
    created_at: str
    updated_at: str


class ChatSessionsResponse(BaseModel):
    """Chat sessions response model."""
    sessions: List[ChatSession]


class CreateChatSessionRequest(BaseModel):
    """Create chat session request model."""
    title: Optional[str] = None


class CreateChatSessionResponse(BaseModel):
    """Create chat session response model."""
    session: ChatSession


class ErrorResponse(BaseModel):
    """Error response model."""
    detail: str

