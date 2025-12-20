"""Prompt registry utility for managing MLflow prompts with fallback support."""
import logging
from typing import Optional, Dict
import mlflow
from mlflow.tracking import MlflowClient

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
            "If the question is ambiguous or missing critical information needed to answer, set requires_clarification=True "
            "and provide a specific clarification_question to ask the user."
        ),
        "general-answer-agent": (
            "Answer the user's general question directly and accurately. "
            "Provide clear, helpful information without using any database tools."
        ),
        "database-query-agent": (
            "Generate an appropriate SQL query to answer the user's database question. "
            "The database has a table called 'iris' with columns: id, sepal_length, sepal_width, "
            "petal_length, petal_width, species. "
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
        tags: Optional[Dict[str, str]] = None
    ) -> None:
        """
        Register a prompt in MLflow if it doesn't already exist.
        
        Args:
            name: Prompt name
            template: Prompt template text
            commit_message: Commit message for the prompt version
            tags: Optional tags to apply to the prompt
        """
        if self._client is None:
            logger.warning(f"MLflow client not available. Skipping registration of prompt '{name}'. Using fallback.")
            return
        
        try:
            if not self._prompt_exists(name):
                mlflow.genai.register_prompt(
                    name=name,
                    template=template,
                    commit_message=commit_message,
                    tags=tags or {}
                )
                logger.info(f"Registered prompt '{name}' in MLflow.")
            else:
                logger.debug(f"Prompt '{name}' already exists in MLflow. Skipping registration.")
        except Exception as e:
            logger.warning(f"Failed to register prompt '{name}' in MLflow: {e}. Will use fallback prompt.")
    
    def get_prompt_template(self, name: str) -> str:
        """
        Get prompt template string from MLflow or fallback.
        
        Args:
            name: Prompt name
            
        Returns:
            Prompt template string
        """
        # Try to load from MLflow first
        try:
            prompt = mlflow.genai.load_prompt(f"prompts:/{name}@latest")
            template = prompt.template
            if isinstance(template, str):
                return template
            elif isinstance(template, list):
                # Chat prompt format - convert to string
                # This is a simple conversion; may need refinement based on actual usage
                return "\n".join([f"{msg.get('role', 'user')}: {msg.get('content', '')}" for msg in template])
            else:
                raise ValueError(f"Unexpected template type: {type(template)}")
        except Exception as e:
            logger.warning(f"Failed to load prompt '{name}' from MLflow: {e}. Using fallback prompt.")
            # Fallback to hardcoded prompt
            if name in self.FALLBACK_PROMPTS:
                return self.FALLBACK_PROMPTS[name]
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
    
    def initialize_all_prompts(self) -> None:
        """
        Initialize all prompts in MLflow registry using fallback templates.
        This should be called during application startup.
        """
        for name, template in self.FALLBACK_PROMPTS.items():
            self.register_prompt_if_missing(
                name=name,
                template=template,
                commit_message="Initial version from codebase",
                tags={"source": "codebase", "agent": name}
            )

