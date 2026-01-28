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
    
    def get_schema_summary(self) -> str:
        """
        Get a lightweight summary of the database schema.
        Returns only table names and brief descriptions.
        
        Returns:
            Summary string with database name, description, and table list
        """
        if self.database_pack is None:
            return ""
        
        return DatabasePackLoader.format_pack_summary(self.database_pack)
    
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
        
        # Find the table
        table = None
        for t in self.database_pack.tables:
            if t.name.lower() == table_name.lower():
                table = t
                break
        
        if table is None:
            available_tables = ", ".join([t.name for t in self.database_pack.tables])
            return f"Table '{table_name}' not found. Available tables: {available_tables}"
        
        # Format table schema
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
        
        return "\n".join(lines)
    
    def get_full_schema(self) -> str:
        """
        Get the complete database schema with all tables and relationships.
        Use this when you need comprehensive schema information.
        
        Returns:
            Complete formatted schema string
        """
        if self.database_pack is None:
            return "No database schema available."
        
        return DatabasePackLoader.format_pack_for_prompt(self.database_pack, format="detailed")
    
    def list_tables(self) -> list[str]:
        """
        Get a list of all available table names.
        
        Returns:
            List of table names
        """
        if self.database_pack is None:
            return []
        
        return [table.name for table in self.database_pack.tables]
