"""Schema loading tools for progressive disclosure of database schema information."""
import logging
from typing import Optional
from app.core.schema_skills import SchemaSkill
from app.core.models import DatabasePack

logger = logging.getLogger(__name__)


class SchemaTool:
    """
    Tool for loading database schema information on-demand.
    Implements progressive disclosure pattern - agents load schema only when needed.
    """
    
    def __init__(self, schema_skill: SchemaSkill):
        """
        Initialize the schema tool with a schema skill instance.
        
        Args:
            schema_skill: SchemaSkill instance that manages schema information
        """
        self.schema_skill = schema_skill
    
    def load_table_schema(self, table_name: str) -> str:
        """
        Load full schema information for a specific table.
        
        Use this when you need detailed information about a specific table's columns,
        types, descriptions, and relationships.
        
        Args:
            table_name: Name of the table to load schema for (e.g., "iris", "postal_code_income")
            
        Returns:
            Formatted string with complete table schema information
        """
        logger.info(f"SchemaTool.load_table_schema called for table: {table_name}")
        return self.schema_skill.get_table_schema(table_name)
    
    def load_full_schema(self) -> str:
        """
        Load the complete database schema with all tables, columns, and relationships.
        
        Use this when you need comprehensive schema information for complex queries
        involving multiple tables or when you're unsure which tables to query.
        
        Returns:
            Formatted string with complete database schema
        """
        logger.info("SchemaTool.load_full_schema called")
        return self.schema_skill.get_full_schema()
    
    def list_tables(self) -> str:
        """
        Get a list of all available table names.
        
        Use this to discover what tables are available in the database.
        
        Returns:
            Formatted string listing all available tables
        """
        logger.info("SchemaTool.list_tables called")
        tables = self.schema_skill.list_tables()
        if not tables:
            return "No tables available in the database."
        
        return f"Available tables: {', '.join(tables)}"
    
    def get_schema_summary(self) -> str:
        """
        Get a lightweight summary of the database schema.
        Returns only database name, description, and table names with brief descriptions.
        
        Use this when you need a quick overview of what data is available without
        detailed column information.
        
        Returns:
            Summary string with database name, description, and table list with descriptions
        """
        logger.info("SchemaTool.get_schema_summary called")
        result = self.schema_skill.get_schema_summary()
        # Log cache status (will be logged by SchemaSkill, but add context here)
        return result
