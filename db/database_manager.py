"""General database management for MyDataBase.db."""
import sqlite3
from pathlib import Path
from typing import Optional, List, Tuple


class DatabaseManager:
    """Manages database operations for MyDataBase.db with support for multiple data sources."""
    
    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize the database manager.
        
        Args:
            db_path: Path to SQLite database file. If None, uses default db/MyDataBase.db
        """
        if db_path is None:
            db_folder = Path(__file__).parent
            db_path = db_folder / "MyDataBase.db"
        
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
    
    def get_connection(self) -> sqlite3.Connection:
        """
        Get a database connection.
        
        Returns:
            SQLite connection object
        """
        conn = sqlite3.connect(self.db_path)
        return conn
    
    def table_exists(self, table_name: str) -> bool:
        """
        Check if a table exists in the database.
        
        Args:
            table_name: Name of the table to check
            
        Returns:
            True if table exists, False otherwise
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name=?
        """, (table_name,))
        result = cursor.fetchone() is not None
        conn.close()
        return result
    
    def create_table(self, table_name: str, schema: str, if_not_exists: bool = True) -> None:
        """
        Create a table in the database.
        
        Args:
            table_name: Name of the table to create
            schema: SQL CREATE TABLE statement (without CREATE TABLE part)
            if_not_exists: If True, adds IF NOT EXISTS clause
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if if_not_exists:
            query = f"CREATE TABLE IF NOT EXISTS {table_name} {schema}"
        else:
            query = f"CREATE TABLE {table_name} {schema}"
        
        cursor.execute(query)
        conn.commit()
        conn.close()
    
    def execute(self, query: str, parameters: Optional[Tuple] = None) -> None:
        """
        Execute a SQL query.
        
        Args:
            query: SQL query string
            parameters: Optional tuple of parameters for parameterized queries
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if parameters:
            cursor.execute(query, parameters)
        else:
            cursor.execute(query)
        
        conn.commit()
        conn.close()
    
    def executemany(self, query: str, parameters: List[Tuple]) -> None:
        """
        Execute a SQL query multiple times with different parameters.
        
        Args:
            query: SQL query string
            parameters: List of parameter tuples
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.executemany(query, parameters)
        conn.commit()
        conn.close()
    
    def get_cursor(self) -> sqlite3.Cursor:
        """
        Get a cursor for manual transaction management.
        Use with context manager or ensure commit/close.
        
        Returns:
            Tuple of (connection, cursor)
        """
        conn = self.get_connection()
        return conn, conn.cursor()
