"""FastAPI application with chat and authentication endpoints."""
from fastapi import FastAPI, Depends, HTTPException, status, Query
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
import os
import uuid
import json
import logging
from dotenv import load_dotenv
from typing import Optional, List
from pydantic_ai import ModelMessage, UserPromptPart, TextPart, ModelRequest, ModelResponse

logger = logging.getLogger(__name__)

from app.api.models import (
    LoginRequest,
    LoginResponse,
    ChatRequest,
    ChatResponse,
    ChatHistoryResponse,
    ChatMessage,
    ChatSession,
    ChatSessionsResponse,
    CreateChatSessionRequest,
    CreateChatSessionResponse,
    ErrorResponse
)
from app.core.auth import (
    create_access_token,
    get_current_user_optional,
    ensure_admin_user,
    ACCESS_TOKEN_EXPIRE_HOURS
)
from app.db.manager import DatabaseManager
from app.agents.orchestrator import OrchestratorAgent
from app.core.models import UserMessage
from app.utils.plot_generator import _make_json_serializable
load_dotenv()

# Configure logging to see logs in console
# Must be configured before other modules create loggers
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    force=True  # Override any existing configuration
)

# Set log level for application modules to ensure visibility
# This ensures logs from our application modules are shown
for module_name in ['app', 'app.api', 'app.agents', 'app.utils', 'app.db', 'app.core']:
    logging.getLogger(module_name).setLevel(logging.INFO)
    logging.getLogger(module_name).propagate = True

# Suppress httpx INFO logs (only show WARNING and above)
logging.getLogger("httpx").setLevel(logging.WARNING)

app = FastAPI(title="Agent app API", version="1.0.0")

# CORS configuration - Simplified for development
# Allow all origins for browser access during development
# Note: When allow_credentials=True, we can't use ["*"], so we use a regex pattern
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r".*",  # Allow all origins (regex pattern)
    allow_credentials=True,
    allow_methods=["*"],  # Allow all methods
    allow_headers=["*"],  # Allow all headers
)

# Initialize database and ensure admin user exists
db = DatabaseManager()
ensure_admin_user(db)

# Initialize orchestrator agent
orchestrator = OrchestratorAgent(
    instructions='Be helpful and concise.'
)

# Test log to verify logging is working
logger.info("API application initialized - logging is configured")


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.post("/api/auth/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """
    Authenticate user and return JWT token.
    For development: just username, no password required.
    
    Args:
        request: Login request with username
        
    Returns:
        JWT token and user information
    """
    # Get user from database (or create if doesn't exist)
    user = db.get_user_by_username(request.username)
    if user is None:
        # Auto-create user for development
        db.create_user(request.username)
        user = db.get_user_by_username(request.username)
    
    # Create access token
    access_token_expires = timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    access_token = create_access_token(
        data={"sub": user["username"]},
        expires_delta=access_token_expires
    )
    
    # Create session in database
    expires_at = datetime.utcnow() + access_token_expires
    db.create_session(user["id"], access_token, expires_at)
    
    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        user_id=user["id"],
        username=user["username"]
    )


def _convert_history_to_messages(history: List[dict]) -> List[ModelMessage]:
    """
    Convert database chat history to pydantic_ai ModelMessage format.
    
    Args:
        history: List of chat message dicts from database
        
    Returns:
        List of ModelMessage objects
    """
    messages = []
    for msg in history:
        # Add user message
        user_msg = ModelRequest(parts=[UserPromptPart(content=msg["message"])])
        messages.append(user_msg)
        
        # Add assistant response
        assistant_msg = ModelResponse(parts=[TextPart(content=msg["response"])])
        messages.append(assistant_msg)
    
    return messages


@app.post("/api/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user: dict = Depends(get_current_user_optional)
):
    """
    Send a chat message and get a response.
    
    Args:
        request: Chat message request with chat_session_id
        current_user: Current authenticated user
        
    Returns:
        Chat response from the agent
    """
    # Verify chat session belongs to user
    chat_session = db.get_chat_session(request.chat_session_id)
    if not chat_session or chat_session["user_id"] != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found"
        )
    
    # Generate orchestrator session_id using chat_session_id
    session_id = f"chat_session_{request.chat_session_id}"
    
    # Load conversation history from database for this chat session
    history = db.get_chat_history(current_user["id"], request.chat_session_id)
    message_history = _convert_history_to_messages(history) if history else None
    
    # Create user message with session_id and username
    user_message = UserMessage(
        content=request.message, 
        session_id=session_id,
        username=current_user.get("username")
    )
    
    # Get response from orchestrator with message history
    agent_response = await orchestrator.chat(user_message, message_history=message_history)
    
    # Save to database
    intent_type = agent_response.metadata.get("intent_type") if agent_response.metadata else None
    
    # Extract plot_spec if present
    plot_spec_dict = None
    if agent_response.plot_spec:
        try:
            # Defensive checks for plot_spec fields
            if agent_response.plot_spec.spec and agent_response.plot_spec.plot_type:
                plot_spec_dict = {
                    "spec": agent_response.plot_spec.spec,
                    "plot_type": agent_response.plot_spec.plot_type
                }
                # Ensure plot_spec is fully JSON-serializable (convert Sets, frozensets, etc.)
                plot_spec_dict = _make_json_serializable(plot_spec_dict)
                logger.info(f"Extracted plot_spec: type={plot_spec_dict.get('plot_type')}, spec_keys={list(plot_spec_dict.get('spec', {}).keys()) if isinstance(plot_spec_dict.get('spec'), dict) else 'N/A'}")
                
                # Also store in metadata for database storage
                if agent_response.metadata is None:
                    agent_response.metadata = {}
                agent_response.metadata["plot_spec"] = plot_spec_dict
            else:
                logger.warning(f"plot_spec exists but missing required fields: spec={agent_response.plot_spec.spec is not None}, plot_type={agent_response.plot_spec.plot_type is not None}")
        except Exception as e:
            logger.error(f"Error extracting plot_spec: {e}", exc_info=True)
            plot_spec_dict = None
    else:
        logger.info("No plot_spec in agent_response")
    
    # Auto-generate title from first message if session has no title
    if not chat_session["title"] and request.message:
        title = request.message[:50] + ("..." if len(request.message) > 50 else "")
        db.update_chat_session(request.chat_session_id, title=title)
    
    db.create_chat_message(
        user_id=current_user["id"],
        chat_session_id=request.chat_session_id,
        message=request.message,
        response=agent_response.message,
        intent_type=intent_type,
        metadata=agent_response.metadata
    )
    
    return ChatResponse(
        response=agent_response.message,
        intent_type=intent_type,
        metadata=agent_response.metadata,
        plot_spec=plot_spec_dict
    )


@app.get("/api/chat/history", response_model=ChatHistoryResponse)
async def get_chat_history(
    chat_session_id: int = Query(..., description="Chat session ID"),
    current_user: dict = Depends(get_current_user_optional)
):
    """
    Get chat history for a specific chat session.
    
    Args:
        chat_session_id: Chat session ID
        current_user: Current authenticated user
        
    Returns:
        Chat history for the session
    """
    # Verify chat session belongs to user
    chat_session = db.get_chat_session(chat_session_id)
    if not chat_session or chat_session["user_id"] != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found"
        )
    
    messages = db.get_chat_history(current_user["id"], chat_session_id)
    
    chat_messages = []
    for msg in messages:
        # Extract plot_spec from metadata if present
        plot_spec = None
        if msg.get("metadata") and isinstance(msg["metadata"], dict):
            plot_spec = msg["metadata"].get("plot_spec")
            if plot_spec:
                # Validate plot_spec structure
                if isinstance(plot_spec, dict) and "spec" in plot_spec and "plot_type" in plot_spec:
                    logger.info(f"Extracted plot_spec from history: message_id={msg['id']}, plot_type={plot_spec.get('plot_type')}")
                else:
                    logger.warning(f"Invalid plot_spec structure for message_id={msg['id']}: {type(plot_spec)}, keys={list(plot_spec.keys()) if isinstance(plot_spec, dict) else 'N/A'}")
                    # Try to fix if structure is wrong
                    if isinstance(plot_spec, dict) and "spec" not in plot_spec:
                        plot_spec = None
            else:
                logger.info(f"No plot_spec in metadata for message_id={msg['id']}")
        else:
            logger.info(f"No metadata for message_id={msg['id']}")
        
        chat_messages.append(
            ChatMessage(
                id=msg["id"],
                message=msg["message"],
                response=msg["response"],
                intent_type=msg["intent_type"],
                metadata=msg["metadata"],
                plot_spec=plot_spec,
                created_at=msg["created_at"]
            )
        )
    
    return ChatHistoryResponse(messages=chat_messages, chat_session_id=chat_session_id)


@app.post("/api/chat/reset")
async def reset_chat_history(
    chat_session_id: int = Query(..., description="Chat session ID"),
    current_user: dict = Depends(get_current_user_optional)
):
    """
    Reset (delete) chat history for a specific chat session.
    
    Args:
        chat_session_id: Chat session ID
        current_user: Current authenticated user
        
    Returns:
        Confirmation message
    """
    # Verify chat session belongs to user
    chat_session = db.get_chat_session(chat_session_id)
    if not chat_session or chat_session["user_id"] != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found"
        )
    
    deleted_count = db.delete_chat_history(current_user["id"], chat_session_id)
    
    # Clear session state in orchestrator
    session_id = f"chat_session_{chat_session_id}"
    orchestrator.reset(session_id=session_id)
    
    return {"message": f"Deleted {deleted_count} messages", "deleted_count": deleted_count}


@app.post("/api/chat/sessions", response_model=CreateChatSessionResponse)
async def create_chat_session(
    request: CreateChatSessionRequest,
    current_user: dict = Depends(get_current_user_optional)
):
    """
    Create a new chat session.
    
    Args:
        request: Create chat session request with optional title
        current_user: Current authenticated user
        
    Returns:
        Created chat session
    """
    session_id = db.create_chat_session(current_user["id"], title=request.title)
    session = db.get_chat_session(session_id)
    
    return CreateChatSessionResponse(
        session=ChatSession(
            id=session["id"],
            user_id=session["user_id"],
            title=session["title"],
            created_at=session["created_at"],
            updated_at=session["updated_at"]
        )
    )


@app.get("/api/chat/sessions", response_model=ChatSessionsResponse)
async def get_chat_sessions(
    current_user: dict = Depends(get_current_user_optional)
):
    """
    Get all chat sessions for the current user.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        List of chat sessions
    """
    sessions = db.get_chat_sessions(current_user["id"])
    
    chat_sessions = []
    for session in sessions:
        chat_sessions.append(
            ChatSession(
                id=session["id"],
                user_id=session["user_id"],
                title=session["title"],
                created_at=session["created_at"],
                updated_at=session["updated_at"]
            )
        )
    
    return ChatSessionsResponse(sessions=chat_sessions)


@app.get("/api/chat/sessions/{session_id}", response_model=ChatSession)
async def get_chat_session(
    session_id: int,
    current_user: dict = Depends(get_current_user_optional)
):
    """
    Get a specific chat session.
    
    Args:
        session_id: Chat session ID
        current_user: Current authenticated user
        
    Returns:
        Chat session
    """
    session = db.get_chat_session(session_id)
    if not session or session["user_id"] != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found"
        )
    
    return ChatSession(
        id=session["id"],
        user_id=session["user_id"],
        title=session["title"],
        created_at=session["created_at"],
        updated_at=session["updated_at"]
    )


@app.delete("/api/chat/sessions/{session_id}")
async def delete_chat_session(
    session_id: int,
    current_user: dict = Depends(get_current_user_optional)
):
    """
    Delete a chat session and all its messages.
    
    Args:
        session_id: Chat session ID
        current_user: Current authenticated user
        
    Returns:
        Confirmation message
    """
    # Verify chat session belongs to user
    session = db.get_chat_session(session_id)
    if not session or session["user_id"] != current_user["id"]:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Chat session not found"
        )
    
    deleted_count = db.delete_chat_session(session_id)
    
    # Clear session state in orchestrator
    orchestrator_session_id = f"chat_session_{session_id}"
    orchestrator.reset(session_id=orchestrator_session_id)
    
    return {"message": f"Deleted session and {deleted_count} messages", "deleted_count": deleted_count}

