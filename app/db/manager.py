"""Database manager for user, session, and chat message operations."""
import sqlite3
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages database operations for users, sessions, and chat messages."""
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the database manager.
        
        Args:
            db_path: Path to SQLite database file. If None, uses default db/app.db
        """
        if db_path is None:
            project_root = Path(__file__).parent.parent.parent
            db_path = project_root / "db" / "app.db"
        
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize schema
        from app.db.schema import create_schema
        create_schema(self.db_path)
    
    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    # User operations
    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """
        Get user by username.
        
        Args:
            username: Username to lookup
            
        Returns:
            User dict or None if not found
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, created_at FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                "id": row["id"],
                "username": row["username"],
                "created_at": row["created_at"]
            }
        return None
    
    def create_user(self, username: str, password_hash: Optional[str] = None) -> int:
        """
        Create a new user.
        
        Args:
            username: Username
            password_hash: Optional hashed password (not used for now, kept for compatibility)
            
        Returns:
            User ID
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            # Use empty string for existing databases that might have NOT NULL constraint
            # For new databases, NULL is fine
            password_value = password_hash if password_hash is not None else ""
            cursor.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, password_value)
            )
            user_id = cursor.lastrowid
            conn.commit()
            return user_id
        except sqlite3.IntegrityError:
            conn.rollback()
            raise ValueError(f"User {username} already exists")
        finally:
            conn.close()
    
    # Session operations
    def create_session(self, user_id: int, token: str, expires_at: datetime) -> int:
        """
        Create a new session.
        
        Args:
            user_id: User ID
            token: JWT token
            expires_at: Expiration timestamp
            
        Returns:
            Session ID
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO sessions (user_id, token, expires_at) VALUES (?, ?, ?)",
            (user_id, token, expires_at.isoformat())
        )
        session_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return session_id
    
    def get_session_by_token(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Get session by token.
        
        Args:
            token: JWT token
            
        Returns:
            Session dict or None if not found
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, user_id, token, expires_at, created_at FROM sessions WHERE token = ?",
            (token,)
        )
        row = cursor.fetchone()
        conn.close()
        
        if row:
            expires_at = datetime.fromisoformat(row["expires_at"])
            if expires_at > datetime.now():
                return {
                    "id": row["id"],
                    "user_id": row["user_id"],
                    "token": row["token"],
                    "expires_at": expires_at,
                    "created_at": row["created_at"]
                }
        return None
    
    def delete_session(self, token: str) -> None:
        """
        Delete a session.
        
        Args:
            token: JWT token
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sessions WHERE token = ?", (token,))
        conn.commit()
        conn.close()
    
    def cleanup_expired_sessions(self) -> None:
        """Delete expired sessions."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM sessions WHERE expires_at < ?", (datetime.now().isoformat(),))
        conn.commit()
        conn.close()
    
    # Chat session operations
    def create_chat_session(self, user_id: int, title: Optional[str] = None) -> int:
        """
        Create a new chat session.
        
        Args:
            user_id: User ID
            title: Optional session title
            
        Returns:
            Chat session ID
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        now = datetime.now().isoformat()
        cursor.execute(
            "INSERT INTO chat_sessions (user_id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
            (user_id, title, now, now)
        )
        session_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return session_id
    
    def get_chat_sessions(self, user_id: int) -> List[Dict[str, Any]]:
        """
        Get all chat sessions for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            List of chat session dicts, ordered by updated_at DESC
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """SELECT id, user_id, title, created_at, updated_at
               FROM chat_sessions
               WHERE user_id = ?
               ORDER BY updated_at DESC""",
            (user_id,)
        )
        rows = cursor.fetchall()
        conn.close()
        
        sessions = []
        for row in rows:
            sessions.append({
                "id": row["id"],
                "user_id": row["user_id"],
                "title": row["title"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"]
            })
        
        return sessions
    
    def get_chat_session(self, session_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a chat session by ID.
        
        Args:
            session_id: Chat session ID
            
        Returns:
            Chat session dict or None if not found
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, user_id, title, created_at, updated_at FROM chat_sessions WHERE id = ?",
            (session_id,)
        )
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                "id": row["id"],
                "user_id": row["user_id"],
                "title": row["title"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"]
            }
        return None
    
    def update_chat_session(self, session_id: int, title: Optional[str] = None) -> None:
        """
        Update a chat session.
        
        Args:
            session_id: Chat session ID
            title: Optional new title
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        if title is not None:
            cursor.execute(
                "UPDATE chat_sessions SET title = ?, updated_at = ? WHERE id = ?",
                (title, datetime.now().isoformat(), session_id)
            )
        else:
            cursor.execute(
                "UPDATE chat_sessions SET updated_at = ? WHERE id = ?",
                (datetime.now().isoformat(), session_id)
            )
        
        conn.commit()
        conn.close()
    
    def delete_chat_session(self, session_id: int) -> int:
        """
        Delete a chat session and all its messages.
        
        Args:
            session_id: Chat session ID
            
        Returns:
            Number of deleted messages
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Get count of messages before deletion
        cursor.execute("SELECT COUNT(*) FROM chat_messages WHERE chat_session_id = ?", (session_id,))
        message_count = cursor.fetchone()[0]
        
        # Delete session (cascade will delete messages)
        cursor.execute("DELETE FROM chat_sessions WHERE id = ?", (session_id,))
        conn.commit()
        conn.close()
        
        return message_count
    
    # Chat message operations
    def create_chat_message(
        self,
        user_id: int,
        chat_session_id: int,
        message: str,
        response: str,
        intent_type: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> int:
        """
        Create a new chat message.
        
        Args:
            user_id: User ID
            chat_session_id: Chat session ID
            message: User message
            response: Bot response
            intent_type: Intent type (optional)
            metadata: Additional metadata (optional)
            
        Returns:
            Message ID
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        metadata_json = json.dumps(metadata) if metadata else None
        
        # Log if plot_spec is being stored
        if metadata and isinstance(metadata, dict) and "plot_spec" in metadata:
            plot_spec = metadata.get("plot_spec")
            if plot_spec:
                logger.info(f"Storing plot_spec in database: message_id will be assigned, plot_type={plot_spec.get('plot_type') if isinstance(plot_spec, dict) else 'N/A'}")
        
        cursor.execute(
            """INSERT INTO chat_messages (user_id, chat_session_id, message, response, intent_type, metadata)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, chat_session_id, message, response, intent_type, metadata_json)
        )
        message_id = cursor.lastrowid
        
        # Update session's updated_at timestamp
        cursor.execute(
            "UPDATE chat_sessions SET updated_at = ? WHERE id = ?",
            (datetime.now().isoformat(), chat_session_id)
        )
        
        conn.commit()
        conn.close()
        return message_id
    
    def get_chat_history(self, user_id: int, chat_session_id: int, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get chat history for a specific chat session.
        
        Args:
            user_id: User ID
            chat_session_id: Chat session ID
            limit: Maximum number of messages to return (None for all)
            
        Returns:
            List of chat message dicts
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        query = """
            SELECT id, user_id, chat_session_id, message, response, intent_type, metadata, created_at
            FROM chat_messages
            WHERE user_id = ? AND chat_session_id = ?
            ORDER BY created_at ASC
        """
        
        if limit:
            query += f" LIMIT {limit}"
        
        cursor.execute(query, (user_id, chat_session_id))
        rows = cursor.fetchall()
        conn.close()
        
        messages = []
        for row in rows:
            metadata = json.loads(row["metadata"]) if row["metadata"] else None
            
            # Log if plot_spec is being retrieved
            if metadata and isinstance(metadata, dict) and "plot_spec" in metadata:
                plot_spec = metadata.get("plot_spec")
                if plot_spec:
                    logger.info(f"Retrieved plot_spec from database: message_id={row['id']}, plot_type={plot_spec.get('plot_type') if isinstance(plot_spec, dict) else 'N/A'}")
            
            messages.append({
                "id": row["id"],
                "user_id": row["user_id"],
                "chat_session_id": row["chat_session_id"],
                "message": row["message"],
                "response": row["response"],
                "intent_type": row["intent_type"],
                "metadata": metadata,
                "created_at": row["created_at"]
            })
        
        return messages
    
    def delete_chat_history(self, user_id: int, chat_session_id: int) -> int:
        """
        Delete chat history for a specific chat session.
        
        Args:
            user_id: User ID
            chat_session_id: Chat session ID
            
        Returns:
            Number of deleted messages
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM chat_messages WHERE user_id = ? AND chat_session_id = ?",
            (user_id, chat_session_id)
        )
        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()
        return deleted_count

