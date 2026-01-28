"""Schema skills system for progressive disclosure of database schema information."""
import logging
from typing import Optional, Dict
from app.core.models import DatabasePack, TableInfo
from app.core.pack_loader import DatabasePackLoader

logger = logging.getLogger(__name__)


class SchemaSkill:
    """
    Manages database schema information as skills for progressive disclosure.
    Provides lightweight summaries and on-demand detailed schema loading.
    """
    
    def __init__(self, database_pack: Optional[DatabasePack] = None):
        """
        Initialize the schema skill with a database pack.
        
        Args:
            database_pack: Optional DatabasePack instance. If None, schema methods return empty strings.
        """
        self.database_pack = database_pack
        # Initialize cache variables for schema methods
        self._cached_summary: Optional[str] = None
        self._cached_full_schema: Optional[str] = None
        self._cached_tables: Optional[list[str]] = None
        self._cached_table_schemas: Dict[str, str] = {}
    
    def get_schema_summary(self) -> str:
        """
        Get a lightweight summary of the database schema.
        Returns only table names and brief descriptions.
        
        Returns:
            Summary string with database name, description, and table list
        """
        if self.database_pack is None:
            return ""
        
        # Check cache first
        if self._cached_summary is not None:
            logger.debug("Schema summary cache hit")
            return self._cached_summary
        
        # Compute and cache
        logger.debug("Schema summary cache miss - computing and caching")
        self._cached_summary = DatabasePackLoader.format_pack_summary(self.database_pack)
        return self._cached_summary
    
    def get_table_schema(self, table_name: str) -> str:
        """
        Get full schema information for a specific table.
        
        Args:
            table_name: Name of the table to get schema for
        
        Returns:
            Formatted string with full table schema, or error message if table not found
        """
        if self.database_pack is None:
            return "No database schema available."
        
        # Normalize table name for cache key (case-insensitive)
        cache_key = table_name.lower()
        
        # Check cache first
        if cache_key in self._cached_table_schemas:
            logger.debug(f"Table schema cache hit for '{table_name}'")
            return self._cached_table_schemas[cache_key]
        
        # Find the table
        table = None
        for t in self.database_pack.tables:
            if t.name.lower() == table_name.lower():
                table = t
                break
        
        if table is None:
            available_tables = ", ".join([t.name for t in self.database_pack.tables])
            error_msg = f"Table '{table_name}' not found. Available tables: {available_tables}"
            # Cache error messages too to avoid repeated lookups
            self._cached_table_schemas[cache_key] = error_msg
            return error_msg
        
        # Format table schema
        logger.debug(f"Table schema cache miss for '{table_name}' - computing and caching")
        lines = [
            f"Table: {table.name}",
            f"Description: {table.description}",
            ""
        ]
        
        lines.append("Columns:")
        for col in table.columns:
            col_info = f"  - {col.name} ({col.type}): {col.description}"
            if col.example_values:
                examples = ", ".join(col.example_values[:3])
                col_info += f" (examples: {examples})"
            lines.append(col_info)
        
        if table.example_queries:
            lines.append("")
            lines.append("Example queries:")
            for query in table.example_queries:
                lines.append(f"  - {query}")
        
        # Add relationships involving this table
        if self.database_pack.relationships:
            related_rels = [
                rel for rel in self.database_pack.relationships
                if rel.from_table == table.name or rel.to_table == table.name
            ]
            if related_rels:
                lines.append("")
                lines.append("Relationships:")
                for rel in related_rels:
                    lines.append(f"  {rel.from_table} -> {rel.to_table} ({rel.type})")
                    lines.append(f"    Description: {rel.description}")
                    lines.append("    Join columns:")
                    for join_col in rel.join_columns:
                        join_info = f"      - {rel.from_table}.{join_col.from_column} = {rel.to_table}.{join_col.to_column}"
                        if join_col.description:
                            join_info += f" ({join_col.description})"
                        lines.append(join_info)
                    if rel.example_queries:
                        lines.append("    Example queries:")
                        for query in rel.example_queries[:2]:  # Limit to 2 examples
                            lines.append(f"      - {query}")
        
        result = "\n".join(lines)
        # Cache the result
        self._cached_table_schemas[cache_key] = result
        return result
    
    def get_full_schema(self) -> str:
        """
        Get the complete database schema with all tables and relationships.
        Use this when you need comprehensive schema information.
        
        Returns:
            Complete formatted schema string
        """
        if self.database_pack is None:
            return "No database schema available."
        
        # Check cache first
        if self._cached_full_schema is not None:
            logger.debug("Full schema cache hit")
            return self._cached_full_schema
        
        # Compute and cache
        logger.debug("Full schema cache miss - computing and caching")
        self._cached_full_schema = DatabasePackLoader.format_pack_for_prompt(self.database_pack, format="detailed")
        return self._cached_full_schema
    
    def list_tables(self) -> list[str]:
        """
        Get a list of all available table names.
        
        Returns:
            List of table names
        """
        if self.database_pack is None:
            return []
        
        # Check cache first
        if self._cached_tables is not None:
            logger.debug("Tables list cache hit")
            return self._cached_tables
        
        # Compute and cache
        logger.debug("Tables list cache miss - computing and caching")
        self._cached_tables = [table.name for table in self.database_pack.tables]
        return self._cached_tables
