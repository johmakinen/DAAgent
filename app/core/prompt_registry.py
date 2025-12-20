"""Prompt registry utility for managing MLflow prompts with fallback support."""
import logging
from typing import Optional, Dict
import mlflow
from mlflow.tracking import MlflowClient
from app.core.models import DatabasePack
from app.core.pack_loader import DatabasePackLoader

logger = logging.getLogger(__name__)


class PromptRegistry:
    """
    Manages MLflow prompt registry operations with graceful fallback to hardcoded prompts.
    
    Handles prompt registration and loading, falling back to hardcoded templates
    if MLflow is unavailable or prompts don't exist.
    """
    
    # Fallback prompts (current hardcoded versions)
    FALLBACK_PROMPTS: Dict[str, str] = {
        "intent-agent": (
            "Analyze the user's question and classify the intent. "
            "Determine if the question is clear enough to proceed or if clarification is needed.\n\n"
            "Intent types:\n"
            "- 'database_query': Questions requiring database access (e.g., 'How many records?', 'Show me data about X')\n"
            "- 'general_question': General questions not requiring database (e.g., 'What is Python?', 'Explain ML')\n\n"
            "{database_pack}\n"
            "IMPORTANT: If database information is provided above, that means a database IS connected and available. "
            "You should proceed with database queries using this connected database WITHOUT asking which dataset to use. "
            "The user's question should be answered using the connected database shown in the database information.\n\n"
            "Only set requires_clarification=True if:\n"
            "- The question is truly ambiguous and cannot be answered even with the available database schema\n"
            "- The question refers to specific information (like column values) that would require user input to narrow down\n"
            "- The question mentions entities or concepts not present in the connected database\n\n"
            "Do NOT ask for clarification about which dataset to use if database information is provided. "
            "The connected database should be used automatically. "
            "When asking for clarification, use the available database information to ask specific questions "
            "(e.g., 'Which species are you interested in?' if the database has a species column and the question is about a specific species)."
        ),
        "database-query-agent": (
            "Generate an appropriate SQL query to answer the user's database question.\n\n"
            "{database_pack}\n"
            "After generating the query, execute it using the query_database tool. "
            "Then format your response as QueryAgentOutput with: "
            "- sql_query: The SQL query you generated and executed "
            "- query_result: The DatabaseResult returned from the tool "
            "- explanation: A brief explanation of what the query does"
        ),
        "synthesizer-agent": (
            "Synthesize a clear, natural language response for the user based on the agent output. "
            "If the output contains database results, present them in a readable format. "
            "If it's a general answer, present it clearly. "
            "Make the response conversational and helpful."
        ),
    }
    
    def __init__(self):
        """Initialize the prompt registry."""
        self._client: Optional[MlflowClient] = None
        try:
            self._client = MlflowClient()
        except Exception as e:
            logger.warning(f"Failed to initialize MLflow client: {e}. Will use fallback prompts.")
    
    def _prompt_exists(self, name: str) -> bool:
        """
        Check if a prompt exists in MLflow registry.
        
        Args:
            name: Prompt name to check
            
        Returns:
            True if prompt exists, False otherwise
        """
        try:
            # Try to load the prompt - if it exists, this will succeed
            mlflow.genai.load_prompt(f"prompts:/{name}@latest")
            return True
        except Exception:
            # Prompt doesn't exist or MLflow is unavailable
            return False
    
    def register_prompt_if_missing(
        self,
        name: str,
        template: str,
        commit_message: str = "Initial version",
        tags: Optional[Dict[str, str]] = None,
        force_update: bool = False
    ) -> None:
        """
        Register a prompt in MLflow if it doesn't already exist, or update it if force_update is True.
        
        Args:
            name: Prompt name
            template: Prompt template text
            commit_message: Commit message for the prompt version
            tags: Optional tags to apply to the prompt
            force_update: If True, register a new version even if prompt exists
        """
        if self._client is None:
            logger.warning(f"MLflow client not available. Skipping registration of prompt '{name}'. Using fallback.")
            return
        
        try:
            if not self._prompt_exists(name) or force_update:
                mlflow.genai.register_prompt(
                    name=name,
                    template=template,
                    commit_message=commit_message,
                    tags=tags or {}
                )
                if force_update:
                    logger.info(f"Updated prompt '{name}' in MLflow with new version.")
                else:
                    logger.info(f"Registered prompt '{name}' in MLflow.")
            else:
                logger.debug(f"Prompt '{name}' already exists in MLflow. Skipping registration.")
        except Exception as e:
            logger.warning(f"Failed to register prompt '{name}' in MLflow: {e}. Will use fallback prompt.")
    
    def _format_prompt_with_pack(self, template: str, pack: Optional[DatabasePack]) -> str:
        """
        Format a prompt template by replacing {database_pack} placeholder with pack information.
        
        Args:
            template: Prompt template string (may contain {database_pack} placeholder)
            pack: Optional database pack to inject
            
        Returns:
            Formatted prompt string with pack information injected
        """
        if pack is None:
            # Remove the placeholder if no pack is provided
            return template.replace("{database_pack}\n", "").replace("{database_pack}", "")
        
        pack_info = DatabasePackLoader.format_pack_for_prompt(pack)
        if pack_info:
            # Format based on context
            if "intent-agent" in template or "Available database information" in template:
                formatted_info = f"Available database information:\n{pack_info}\n"
            else:
                formatted_info = f"Database schema:\n{pack_info}\n"
            
            return template.replace("{database_pack}", formatted_info)
        
        return template.replace("{database_pack}\n", "").replace("{database_pack}", "")
    
    def get_prompt_template(self, name: str, database_pack: Optional[DatabasePack] = None) -> str:
        """
        Get prompt template string from MLflow or fallback.
        
        Args:
            name: Prompt name
            database_pack: Optional database pack to inject into the prompt
            
        Returns:
            Prompt template string with pack information injected if provided
        """
        # Try to load from MLflow first
        try:
            prompt = mlflow.genai.load_prompt(f"prompts:/{name}@latest")
            template = prompt.template
            if isinstance(template, str):
                return self._format_prompt_with_pack(template, database_pack)
            elif isinstance(template, list):
                # Chat prompt format - convert to string
                # This is a simple conversion; may need refinement based on actual usage
                template_str = "\n".join([f"{msg.get('role', 'user')}: {msg.get('content', '')}" for msg in template])
                return self._format_prompt_with_pack(template_str, database_pack)
            else:
                raise ValueError(f"Unexpected template type: {type(template)}")
        except Exception as e:
            logger.warning(f"Failed to load prompt '{name}' from MLflow: {e}. Using fallback prompt.")
            # Fallback to hardcoded prompt
            if name in self.FALLBACK_PROMPTS:
                template = self.FALLBACK_PROMPTS[name]
                return self._format_prompt_with_pack(template, database_pack)
            else:
                logger.error(f"No fallback prompt found for '{name}'")
                raise ValueError(f"Prompt '{name}' not found in MLflow and no fallback available.")
    
    def load_prompt(self, name: str):
        """
        Load prompt object from MLflow or return None if unavailable.
        
        Args:
            name: Prompt name
            
        Returns:
            MLflow prompt object or None if unavailable
        """
        try:
            return mlflow.genai.load_prompt(f"prompts:/{name}@latest")
        except Exception as e:
            logger.debug(f"Could not load prompt object '{name}' from MLflow: {e}")
            return None
    
    def initialize_all_prompts(self, force_update: bool = False) -> None:
        """
        Initialize all prompts in MLflow registry using fallback templates.
        This should be called during application startup.
        
        Args:
            force_update: If True, update existing prompts with new versions from codebase
        """
        for name, template in self.FALLBACK_PROMPTS.items():
            self.register_prompt_if_missing(
                name=name,
                template=template,
                commit_message="Initial version from codebase" if not force_update else "Updated version from codebase",
                tags={"source": "codebase", "agent": name},
                force_update=force_update
            )

