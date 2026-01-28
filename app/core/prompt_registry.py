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
        "planner-agent": (
            "Create a structured execution plan for the user's question.\n\n"
            "1. INTENT: Classify as 'database_query' if the question requires database data, including:\n"
            "   - Questions asking for data from tables/columns\n"
            "   - Questions requesting plots/visualizations that need database data (histograms, bar charts, line plots, scatter plots)\n"
            "   - Questions about aggregations, counts, or statistics from the database\n"
            "   Classify as 'general_question' only for questions that don't require any database data.\n\n"
            "{database_pack}\n"
            "If database information is provided, use it automatically without asking which dataset to use.\n\n"
            "2. CACHED DATA: Set use_cached_data=True when user explicitly references previous data "
            "('plot that', 'visualize those results', 'show a chart of the data'). "
            "Set cached_data_key='latest' when use_cached_data=True.\n\n"
            "3. PLOT REQUIREMENTS: Set requires_plot=True for: trends (line), distributions (histogram), "
            "comparisons (bar), relationships (scatter). Set requires_plot=False for simple counts or single values.\n"
            "   IMPORTANT: If requires_plot=True, the intent_type should typically be 'database_query' since plots need data.\n\n"
            "4. SQL QUERY: If intent_type='database_query' and use_cached_data=False, generate SQL in sql_query field.\n\n"
            "5. CLARIFICATION: Only set requires_clarification=True if question is truly ambiguous.\n\n"
            "Provide clear reasoning in the 'reasoning' field."
        ),
        "database-query-agent": (
            "Generate an appropriate SQL query to answer the user's database question.\n\n"
            "{database_pack}\n"
            "After generating the query, execute it using the query_database tool. "
            "Then format your response as QueryAgentOutput with: "
            "- sql_query: The SQL query you generated and executed "
            "- query_result: The DatabaseResult returned from the query_database tool "
            "- explanation: A brief explanation of what the query does"
        ),
        "synthesizer-agent": (
            "Synthesize a clear, concise response for the user based on the agent output.\n\n"
            "RULES:\n"
            "- Present the answer directly without asking unnecessary questions\n"
            "- Extract and present the ACTUAL VALUES from the query result data - do not use placeholders or column names as values\n"
            "- When presenting results, use the actual numeric values, strings, and data from the query result\n"
            "- Do NOT show raw data, tables, or row-by-row listings in a tabular format\n"
            "- Format the response naturally, extracting specific values from the data (e.g., 'Setosa: 4.4' not 'Setosa: max_sepal_width')\n"
            "- If a plot was generated, mention it in present tense (e.g., 'Here is the plot...' not 'I'll generate...')\n"
            "- Be concise and avoid verbose explanations\n"
            "- Only ask for clarification if truly needed\n\n"
            "PLOT DECISION:\n"
            "If the execution plan specifies requires_plot=True, a plot will be generated automatically - you don't need to set should_generate_plot.\n"
            "If the context includes database query results and no execution plan plot requirement, consider if a plot would help. "
            "Set should_generate_plot=True for: trends (line), distributions (histogram), comparisons (bar), relationships (scatter). "
            "Set should_generate_plot=False for: simple counts, single values, or when visualization doesn't help. "
            "If should_generate_plot=True, specify plot_type and optional plot_columns."
        ),
        "plot-planning-agent": (
            "Analyze the user's question and available data columns to determine the optimal plot configuration.\n\n"
            "YOUR TASK:\n"
            "1. Determine which columns should be used for the plot based on the user's question\n"
            "2. Identify if grouping/color encoding is needed by analyzing phrases like:\n"
            "   - 'for the three species' → grouping_column='species'\n"
            "   - 'by species' → grouping_column='species'\n"
            "   - 'across categories' → look for categorical column\n"
            "   - 'for each X' → grouping_column=X\n"
            "   - 'compare X across Y' → grouping_column=Y\n"
            "   - 'distributions of Y for X' → grouping_column=X\n"
            "3. Match column names from the question to available columns (handle plurals, articles, partial matches)\n"
            "4. Assign x_column and y_column appropriately based on plot type:\n"
            "   - Histogram: x_column = quantitative column, y_column = None (uses count)\n"
            "   - Bar: x_column = categorical, y_column = quantitative (or count)\n"
            "   - Line: x_column = ordinal/numeric, y_column = quantitative\n"
            "   - Scatter: x_column = quantitative, y_column = quantitative\n"
            "5. Set grouping_column only when the question clearly indicates grouping is needed\n"
            "6. Include all relevant columns in the columns list\n\n"
            "EXAMPLES:\n"
            "- Question: 'Show me the distributions of sepal lengths for the three species'\n"
            "  → plot_type='histogram', x_column='sepal_length', grouping_column='species'\n"
            "- Question: 'Histogram of petal width by species'\n"
            "  → plot_type='histogram', x_column='petal_width', grouping_column='species'\n"
            "- Question: 'Compare sepal length across species'\n"
            "  → plot_type='histogram' or 'bar', x_column='sepal_length', grouping_column='species'\n\n"
            "Provide clear reasoning for your decisions."
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

