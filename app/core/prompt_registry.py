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
            "OUTPUT FORMAT:\n"
            "- If the question is clear and you have enough information: Output an ExecutionPlan object\n"
            "- If the question is ambiguous or missing critical information: Output a STRING containing a clear clarification question\n"
            "  When outputting a clarification string, do NOT call schema tools repeatedly. Simply ask the user directly what information you need.\n\n"
            "1. DATA AVAILABILITY CHECK (CRITICAL):\n"
            "   - ALWAYS check if the requested data exists in the database schema before creating an ExecutionPlan\n"
            "   - Use the get_schema_summary tool to understand what tables and data are available\n"
            "   - If the user asks for data that does NOT exist in any table (e.g., 'population' when only 'income' and 'apartment_m2' exist):\n"
            "     * DO NOT create an ExecutionPlan\n"
            "     * Output a STRING clarification that:\n"
            "       - Clearly states that the requested data is not available\n"
            "       - Lists what data IS available in the database\n"
            "       - Asks the user what they would like instead\n"
            "     * Example: 'I don't have population data for postal codes. However, I do have income data (postal_code_income table) and average apartment size data (postal_code_apartment_m2 table) for postal codes. Would you like to see income or apartment size data for postal code 02650 in 2024 instead?'\n"
            "   - Only create an ExecutionPlan if the requested data exists in the database schema\n\n"
            "2. INTENT: Classify as 'database_query' if the question requires database data, including:\n"
            "   - Questions asking for data from tables/columns\n"
            "   - Questions requesting plots/visualizations that need database data (histograms, bar charts, line plots, scatter plots)\n"
            "   - Questions about aggregations, counts, or statistics from the database\n"
            "   Classify as 'general_question' only for questions that don't require any database data.\n\n"
            "{database_pack}\n"
            "If database information is provided, use it automatically without asking which dataset to use.\n\n"
            "3. CACHED DATA: Set use_cached_data=True when user explicitly references previous data "
            "('plot that', 'visualize those results', 'show a chart of the data'). "
            "Set cached_data_key='latest' when use_cached_data=True.\n\n"
            "4. PLOT REQUIREMENTS: Set requires_plot=True for: trends (line), distributions (histogram), "
            "comparisons (bar), relationships (scatter). Set requires_plot=False for simple counts or single values.\n"
            "   IMPORTANT: If requires_plot=True, the intent_type should typically be 'database_query' since plots need data.\n\n"
            "5. CLARIFICATION: If the question is ambiguous or missing critical information (e.g., missing year, unclear column name, etc.),\n"
            "   output a STRING with a clear, helpful clarification question. Do NOT output an ExecutionPlan.\n"
            "   Example clarification: 'Please specify the year for which you want the income to apartment size ratio for postal code area 00100. The data is stored in long format across multiple years.'\n\n"
            "When outputting an ExecutionPlan, provide clear reasoning in the 'reasoning' field explaining your decision."
        ),
        "database-query-agent": (
            "Generate an appropriate SQL query to answer the user's database question.\n\n"
            "SCHEMA ACCESS:\n"
            "You have access to schema loading tools. ALWAYS use them BEFORE generating your first query:\n"
            "- Use list_tables() to see available tables\n"
            "- Use load_table_schema(table_name) to get detailed schema for a specific table\n"
            "- Use load_full_schema() to get complete database schema (use when querying multiple tables)\n\n"
            "IMPORTANT - SCHEMA CHECKING:\n"
            "- Pay close attention to example values in the schema - they help match user input to correct columns\n"
            "- When user mentions a value like '00100', check which column has that value in its examples\n"
            "- Example values are shown in the schema output when you use load_table_schema()\n"
            "- If user says 'postal code area 00100', match '00100' against example values to find the correct column\n\n"
            "QUERY EXECUTION AND RETRY:\n"
            "1. After generating the query, execute it using the query_database tool\n"
            "2. Check query_result.success - if False, the query failed\n"
            "3. When a query fails:\n"
            "   - Analyze the error message (e.g., 'no such column: postal_code_area')\n"
            "   - Use schema tools to understand the correct column/table names\n"
            "   - Pay attention to example values to match user input correctly\n"
            "   - CRITICAL: You MUST call query_database again with the corrected query\n"
            "   - Do NOT just mention the corrected query in your explanation - you MUST execute it\n"
            "   - The corrected query must be executed via query_database tool, not just described\n"
            "4. You have a MAXIMUM of 3 total attempts (initial query + up to 2 retries)\n"
            "5. After 3 failed attempts:\n"
            "   - Use schema tools to find possible column names that match the error\n"
            "   - Generate a clarification question like: 'Do you mean 'postal_code' or 'postal_area'? Both are in the table 'postal_code_income'.'\n"
            "   - Set requires_clarification=True and clarification_question in your QueryAgentOutput\n"
            "   - Include the last attempted sql_query and query_result in your output\n\n"
            "OUTPUT FORMAT:\n"
            "Format your response as QueryAgentOutput with: "
            "- sql_query: The SQL query you generated and executed (or last attempted query if all retries failed)\n"
            "- query_result: The DatabaseResult returned from the query_database tool (from the last attempt)\n"
            "- explanation: A brief explanation of what the query does\n"
            "- requires_clarification: Set to True only if all 3 attempts failed and you need user clarification\n"
            "- clarification_question: The clarification question to ask (only set if requires_clarification=True)"
        ),
        "synthesizer-agent": (
            "Synthesize a clear, concise response for the user based on the agent output.\n\n"
            "RULES:\n"
            "- Present the answer directly without asking unnecessary questions\n"
            "- Extract and present the ACTUAL VALUES from the query result data - do not use placeholders or column names as values\n"
            "- When presenting results, use the actual numeric values, strings, and data from the query result\n"
            "- Do NOT show raw data, tables, or row-by-row listings in a tabular format\n"
            "- Format the response naturally, extracting specific values from the data (e.g., 'Setosa: 4.4' not 'Setosa: max_sepal_width')\n"
            "- Be concise and avoid verbose explanations\n"
            "- Only ask for clarification if truly needed\n\n"
            "PLOT EXPLANATION:\n"
            "When the context indicates a plot will be generated, you MUST analyze the actual data values and explain what they show. "
            "DO NOT just say 'a plot has been generated' or 'a line plot will be generated'. Instead:\n"
            "- Analyze the data trends, patterns, and insights from the query result data\n"
            "- Describe specific values, changes, and notable points (e.g., 'Income increased from 14.9k in 2010 to 16.35k in 2024, with a dip to 15.8k in 2021')\n"
            "- Explain what the data means in the context of the user's question\n"
            "- For trends: describe the direction, magnitude, and any significant changes over time\n"
            "- For comparisons: highlight differences between groups\n"
            "- For distributions: describe the shape, range, and central tendencies\n"
            "- Keep the explanation informative and focused on data analysis, not plot generation mechanics\n"
            "- The plot will be displayed automatically - your job is to explain what the data shows\n\n"
            "PLOT DECISION:\n"
            "The execution plan (if provided) takes precedence for plot decisions:\n"
            "- If execution_plan.requires_plot=True: A plot will be generated automatically using the plan's plot_type. "
            "You do NOT need to set should_generate_plot in this case - the plot is handled by the system.\n"
            "- If execution_plan.requires_plot=False or no execution plan is provided: You can decide if a plot would help. "
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
            "6. Include all relevant columns in the columns list\n"
            "7. CRITICAL: Infer meaningful labels from the user's question:\n"
            "   - Extract what the data represents (e.g., 'income' → y_label='Income', 'year' → x_label='Year')\n"
            "   - Use human-readable labels, not column names (e.g., 'Income' not 'value', 'Year' not 'year')\n"
            "   - Capitalize appropriately (e.g., 'Income', 'Year', 'Postal Code')\n"
            "   - Create descriptive titles (e.g., 'Income Trend Over Time', 'Income by Postal Code')\n"
            "   - If the question mentions 'income', 'population', 'price', etc., use those terms in labels\n"
            "   - For time-based plots, use 'Year' or 'Time' for x-axis\n"
            "   - For generic column names like 'value', infer the meaning from context (e.g., if question mentions income, label as 'Income')\n\n"
            "EXAMPLES:\n"
            "- Question: 'Show me the distributions of sepal lengths for the three species'\n"
            "  → plot_type='histogram', x_column='sepal_length', grouping_column='species', x_label='Sepal Length', title='Distribution of Sepal Length by Species'\n"
            "- Question: 'What has been the trend development in the income of the postal code area 00100?'\n"
            "  → plot_type='line', x_column='year', y_column='value', x_label='Year', y_label='Income', title='Income Trend Over Time'\n"
            "- Question: 'Compare sepal length across species'\n"
            "  → plot_type='histogram' or 'bar', x_column='sepal_length', grouping_column='species', x_label='Sepal Length', title='Sepal Length by Species'\n\n"
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
    
    def _format_prompt_with_pack(
        self, 
        template: str, 
        pack: Optional[DatabasePack], 
        schema_level: str = "full"
    ) -> str:
        """
        Format a prompt template by replacing {database_pack} placeholder with pack information.
        
        Args:
            template: Prompt template string (may contain {database_pack} placeholder)
            pack: Optional database pack to inject
            schema_level: Level of schema detail - "none", "summary", or "full"
            
        Returns:
            Formatted prompt string with pack information injected based on schema_level
        """
        if pack is None or schema_level == "none":
            # Remove the placeholder if no pack is provided or schema_level is "none"
            return template.replace("{database_pack}\n", "").replace("{database_pack}", "")
        
        if schema_level == "summary":
            pack_info = DatabasePackLoader.format_pack_summary(pack)
        else:  # schema_level == "full"
            pack_info = DatabasePackLoader.format_pack_for_prompt(pack, format="detailed")
        
        if pack_info:
            # Format based on context
            if "intent-agent" in template or "Available database information" in template:
                formatted_info = f"Available database information:\n{pack_info}\n"
            else:
                formatted_info = f"Database schema:\n{pack_info}\n"
            
            return template.replace("{database_pack}", formatted_info)
        
        return template.replace("{database_pack}\n", "").replace("{database_pack}", "")
    
    def get_prompt_template(
        self, 
        name: str, 
        database_pack: Optional[DatabasePack] = None,
        schema_level: str = "full"
    ) -> str:
        """
        Get prompt template string from MLflow or fallback.
        
        Args:
            name: Prompt name
            database_pack: Optional database pack to inject into the prompt
            schema_level: Level of schema detail - "none", "summary", or "full" (default: "full")
            
        Returns:
            Prompt template string with pack information injected based on schema_level
        """
        # Try to load from MLflow first
        try:
            prompt = mlflow.genai.load_prompt(f"prompts:/{name}@latest")
            template = prompt.template
            if isinstance(template, str):
                return self._format_prompt_with_pack(template, database_pack, schema_level)
            elif isinstance(template, list):
                # Chat prompt format - convert to string
                # This is a simple conversion; may need refinement based on actual usage
                template_str = "\n".join([f"{msg.get('role', 'user')}: {msg.get('content', '')}" for msg in template])
                return self._format_prompt_with_pack(template_str, database_pack, schema_level)
            else:
                raise ValueError(f"Unexpected template type: {type(template)}")
        except Exception as e:
            logger.warning(f"Failed to load prompt '{name}' from MLflow: {e}. Using fallback prompt.")
            # Fallback to hardcoded prompt
            if name in self.FALLBACK_PROMPTS:
                template = self.FALLBACK_PROMPTS[name]
                return self._format_prompt_with_pack(template, database_pack, schema_level)
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

