"""Database pack loader for loading and formatting database schema information."""
import yaml
import logging
from pathlib import Path
from typing import Optional
from app.core.models import DatabasePack

logger = logging.getLogger(__name__)


class DatabasePackLoader:
    """Loader for database packs from YAML files."""
    
    @staticmethod
    def load_pack(pack_path: str) -> DatabasePack:
        """
        Load a database pack from a YAML file.
        
        Args:
            pack_path: Path to the YAML pack file
            
        Returns:
            DatabasePack model instance
            
        Raises:
            FileNotFoundError: If the pack file doesn't exist
            ValueError: If the YAML is invalid or doesn't match the schema
        """
        pack_file = Path(pack_path)
        if not pack_file.exists():
            raise FileNotFoundError(f"Database pack file not found: {pack_path}")
        
        try:
            with open(pack_file, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            # Validate and create DatabasePack model
            pack = DatabasePack(**data)
            logger.info(f"Successfully loaded database pack: {pack.name}")
            return pack
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in pack file {pack_path}: {e}")
        except Exception as e:
            raise ValueError(f"Failed to load database pack from {pack_path}: {e}")
    
    @staticmethod
    def format_pack_for_prompt(pack: Optional[DatabasePack], format: str = "detailed") -> str:
        """
        Format a database pack as text for injection into prompts.
        
        Args:
            pack: DatabasePack instance to format, or None
            format: Format style - "detailed" (full info) or "summary" (brief)
            
        Returns:
            Formatted string representation of the pack, or empty string if pack is None
        """
        if pack is None:
            return ""
        
        if format == "summary":
            # Brief summary format
            lines = [f"Database: {pack.name}", f"Description: {pack.description}"]
            lines.append(f"Tables: {', '.join([t.name for t in pack.tables])}")
            return "\n".join(lines)
        
        # Detailed format (default)
        lines = [
            f"Database: {pack.name}",
            f"Description: {pack.description}",
            ""
        ]
        
        for table in pack.tables:
            lines.append(f"Table: {table.name}")
            lines.append(f"  Description: {table.description}")
            lines.append("  Columns:")
            for col in table.columns:
                col_info = f"    - {col.name} ({col.type}): {col.description}"
                if col.example_values:
                    examples = ", ".join(col.example_values[:3])  # Show max 3 examples
                    col_info += f" (examples: {examples})"
                lines.append(col_info)
            
            if table.example_queries:
                lines.append("  Example queries:")
                for query in table.example_queries:
                    lines.append(f"    - {query}")
            lines.append("")
        
        # Add relationships information if available
        if pack.relationships:
            lines.append("Relationships:")
            for rel in pack.relationships:
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
                    for query in rel.example_queries:
                        lines.append(f"      - {query}")
                lines.append("")
        
        return "\n".join(lines)

