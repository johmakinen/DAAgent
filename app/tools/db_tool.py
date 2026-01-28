"""Database tool for executing SQL queries with typed inputs and outputs."""
from pathlib import Path
from typing import Optional
import sqlite3
import mlflow
from mlflow.exceptions import MlflowException
import logging

from app.core.models import DatabaseQuery, DatabaseResult

logger = logging.getLogger(__name__)


class DatabaseTool:
    """Tool for executing SQL queries against SQLite database."""
    
    def __init__(self, db_path: Optional[str] = None):
        """
        Initialize the database tool.
        
        Args:
            db_path: Path to SQLite database file. If None, uses default db/MyDataBase.db
        """
        if db_path is None:
            # Default to MyDataBase.db in the db folder
            project_root = Path(__file__).parent.parent.parent
            db_path = project_root / "db" / "MyDataBase.db"
        
        self.db_path = Path(db_path)
        if not self.db_path.exists():
            raise FileNotFoundError(f"Database not found at {self.db_path}")
        
        # Counter for unique parameter names when multiple queries are executed in the same run
        self._query_counter = 0
    
    def _safe_log_param(self, key: str, value: str, use_counter: bool = False) -> None:
        """
        Safely log an MLflow parameter, handling cases where it already exists.
        
        Args:
            key: Parameter key
            value: Parameter value
            use_counter: If True, append counter to key to make it unique
        """
        try:
            if use_counter:
                # Increment counter and use it to make unique parameter names
                self._query_counter += 1
                unique_key = f"{key}_{self._query_counter}"
            else:
                unique_key = key
            
            mlflow.log_param(unique_key, value)
        except MlflowException as e:
            # Parameter already exists with different value - log warning but don't fail
            logger.debug(f"MLflow parameter '{unique_key}' already exists, skipping: {e}")
        except Exception as e:
            # Other MLflow errors - log but don't fail
            logger.debug(f"Failed to log MLflow parameter '{unique_key}': {e}")
    
    @mlflow.trace(name="execute_query")
    def execute_query(self, query: DatabaseQuery) -> DatabaseResult:
        """
        Execute a SQL query and return typed results.
        
        Args:
            query: DatabaseQuery model containing SQL query and parameters
            
        Returns:
            DatabaseResult model with query results or error information
        """
        # Log the SQL query for better tracing (use counter to make unique if needed)
        self._safe_log_param("sql_query", query.query, use_counter=True)
        if query.parameters:
            self._safe_log_param("query_parameters", str(query.parameters), use_counter=True)
        
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
            
            # Log query results metadata
            mlflow.log_metric("row_count", len(data))
            self._safe_log_param("query_success", "True", use_counter=True)
            
            return DatabaseResult(
                success=True,
                data=data,
                row_count=len(data)
            )
            
        except sqlite3.Error as e:
            self._safe_log_param("query_success", "False", use_counter=True)
            self._safe_log_param("query_error", str(e), use_counter=True)
            return DatabaseResult(
                success=False,
                error=str(e),
                row_count=0
            )
        except Exception as e:
            self._safe_log_param("query_success", "False", use_counter=True)
            self._safe_log_param("query_error", f"Unexpected error: {str(e)}", use_counter=True)
            return DatabaseResult(
                success=False,
                error=f"Unexpected error: {str(e)}",
                row_count=0
            )

