"""FastAPI application with chat and authentication endpoints."""
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

from app.api.models import (
    LoginRequest,
    LoginResponse,
    ChatRequest,
    ChatResponse,
    ChatHistoryResponse,
    ChatMessage,
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

load_dotenv()

app = FastAPI(title="Agent app API", version="1.0.0")

# CORS configuration
# Allow all origins in development, restrict in production
# Default includes localhost and common local network IPs
default_origins = [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
    "http://192.168.0.107:3000",  # Common local network IP
    "http://192.168.1.107:3000",  # Alternative common local network IP
]

cors_origins_str = os.getenv("CORS_ORIGINS", ",".join(default_origins))
cors_origins = [origin.strip() for origin in cors_origins_str.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Initialize database and ensure admin user exists
db = DatabaseManager()
ensure_admin_user(db)

# Initialize orchestrator agent
orchestrator = OrchestratorAgent(
    model='azure:gpt-5-nano',
    instructions='Be helpful and concise.'
)


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


@app.post("/api/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    current_user: dict = Depends(get_current_user_optional)
):
    """
    Send a chat message and get a response.
    
    Args:
        request: Chat message request
        current_user: Current authenticated user
        
    Returns:
        Chat response from the agent
    """
    # Create user message
    user_message = UserMessage(content=request.message)
    
    # Get response from orchestrator
    agent_response = await orchestrator.chat(user_message)
    
    # Save to database
    intent_type = agent_response.metadata.get("intent_type") if agent_response.metadata else None
    db.create_chat_message(
        user_id=current_user["id"],
        message=request.message,
        response=agent_response.message,
        intent_type=intent_type,
        metadata=agent_response.metadata
    )
    
    return ChatResponse(
        response=agent_response.message,
        intent_type=intent_type,
        metadata=agent_response.metadata
    )


@app.get("/api/chat/history", response_model=ChatHistoryResponse)
async def get_chat_history(
    current_user: dict = Depends(get_current_user_optional)
):
    """
    Get chat history for the current user.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        Chat history
    """
    messages = db.get_chat_history(current_user["id"])
    
    chat_messages = [
        ChatMessage(
            id=msg["id"],
            message=msg["message"],
            response=msg["response"],
            intent_type=msg["intent_type"],
            metadata=msg["metadata"],
            created_at=msg["created_at"]
        )
        for msg in messages
    ]
    
    return ChatHistoryResponse(messages=chat_messages)


@app.post("/api/chat/reset")
async def reset_chat_history(
    current_user: dict = Depends(get_current_user_optional)
):
    """
    Reset (delete) chat history for the current user.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        Confirmation message
    """
    deleted_count = db.delete_chat_history(current_user["id"])
    return {"message": f"Deleted {deleted_count} messages", "deleted_count": deleted_count}

