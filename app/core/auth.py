"""Simplified authentication utilities for development (no password hashing)."""
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from app.db.manager import DatabaseManager

# JWT settings
SECRET_KEY = "dev-secret-key-change-in-production"  # TODO: Move to environment variable
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 24

# HTTP Bearer token scheme (optional for development)
security = HTTPBearer(auto_error=False)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token.
    
    Args:
        data: Data to encode in token
        expires_delta: Optional expiration delta
        
    Returns:
        JWT token string
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Optional[dict]:
    """
    Decode and verify a JWT token.
    
    Args:
        token: JWT token string
        
    Returns:
        Decoded token payload or None if invalid
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None


def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: DatabaseManager = Depends(lambda: DatabaseManager())
) -> dict:
    """
    Get current user from JWT token if provided, otherwise return default user.
    For development - no strict authentication required.
    
    Args:
        credentials: HTTP Bearer credentials (optional)
        db: Database manager instance
        
    Returns:
        User dict (default admin user if no token provided)
    """
    # If no token provided, return default admin user
    if credentials is None:
        user = db.get_user_by_username("admin")
        if user is None:
            # Create admin user if it doesn't exist
            ensure_admin_user(db)
            user = db.get_user_by_username("admin")
        return user
    
    token = credentials.credentials
    payload = decode_token(token)
    
    if payload is None:
        # Invalid token, return default user
        user = db.get_user_by_username("admin")
        if user is None:
            ensure_admin_user(db)
            user = db.get_user_by_username("admin")
        return user
    
    username: str = payload.get("sub")
    if username is None:
        # Invalid payload, return default user
        user = db.get_user_by_username("admin")
        if user is None:
            ensure_admin_user(db)
            user = db.get_user_by_username("admin")
        return user
    
    # Get user from database
    user = db.get_user_by_username(username)
    if user is None:
        # User not found, return default user
        user = db.get_user_by_username("admin")
        if user is None:
            ensure_admin_user(db)
            user = db.get_user_by_username("admin")
        return user
    
    return user


def ensure_admin_user(db: DatabaseManager) -> None:
    """
    Ensure default admin user exists with username 'admin'.
    No password required for development.
    
    Args:
        db: Database manager instance
    """
    admin_user = db.get_user_by_username("admin")
    if admin_user is None:
        # Create admin user
        db.create_user("admin")
        print("Created default admin user (username: admin)")
