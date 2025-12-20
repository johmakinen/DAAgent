"""Database tool for executing SQL queries with typed inputs and outputs."""
from pathlib import Path
from typing import Optional
import sqlite3

from app.core.models import DatabaseQuery, DatabaseResult


class DatabaseTool:
    """Tool for executing SQL queries against SQLite database."""
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the database tool.
        
        Args:
            db_path: Path to SQLite database file. If None, uses default db/iris_data.db
        """
        if db_path is None:
            # Default to iris_data.db in the db folder
            project_root = Path(__file__).parent.parent.parent
            db_path = project_root / "db" / "iris_data.db"
        
        self.db_path = Path(db_path)
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found at {self.db_path}")
    
    def execute_query(self, query: DatabaseQuery) -> DatabaseResult:
        """
        Execute a SQL query and return typed results.
        
        Args:
            query: DatabaseQuery model containing SQL query and parameters
            
        Returns:
            DatabaseResult model with query results or error information
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row  # Enable column access by name
            cursor = conn.cursor()
            
            # Execute query
            if query.parameters:
                cursor.execute(query.query, query.parameters)
            else:
                cursor.execute(query.query)
            
            # Fetch results
            rows = cursor.fetchall()
            
            # Convert rows to list of dictionaries
            data = [dict(row) for row in rows] if rows else []
            
            conn.close()
            
            return DatabaseResult(
                success=True,
                data=data,
                row_count=len(data)
            )
            
        except sqlite3.Error as e:
            return DatabaseResult(
                success=False,
                error=str(e),
                row_count=0
            )
        except Exception as e:
            return DatabaseResult(
                success=False,
                error=f"Unexpected error: {str(e)}",
                row_count=0
            )

