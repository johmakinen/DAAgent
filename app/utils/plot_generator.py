"""Plot generation utility using Altair to create Vega-Lite specifications."""
import logging
import re
import json
from typing import Optional, List, Dict, Any
import pandas as pd
import altair as alt
from app.core.models import PlotConfig

logger = logging.getLogger(__name__)

PLOT_STYLE_CONFIG = {
                "labelFontSize": 12,
                "titleFontSize": 14,
                "labelFontStyle": 'italic',
                "labelFontWeight": 'bold'
            }

def _make_json_serializable(obj: Any) -> Any:
    """
    Recursively convert non-JSON-serializable objects (like Sets, frozensets) to JSON-serializable types.
    
    Args:
        obj: Object to convert
        
    Returns:
        JSON-serializable version of the object
    """
    # Handle sets and frozensets (convert to list)
    if isinstance(obj, (set, frozenset)):
        return sorted(list(obj)) if obj else []
    # Handle dictionaries (recursively process values)
    elif isinstance(obj, dict):
        return {key: _make_json_serializable(value) for key, value in obj.items()}
    # Handle lists and tuples (recursively process items)
    elif isinstance(obj, (list, tuple)):
        return [_make_json_serializable(item) for item in obj]
    # Handle basic JSON-serializable types
    elif isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    # Handle numpy types and other numeric types
    elif hasattr(obj, 'item'):  # numpy scalar types
        return obj.item()
    elif hasattr(obj, 'tolist'):  # numpy arrays
        return _make_json_serializable(obj.tolist())
    else:
        # For other types, try to convert to string or use JSON serialization
        try:
            # Test if it's already JSON-serializable
            json.dumps(obj)
            return obj
        except (TypeError, ValueError):
            # If it can't be serialized, convert to string representation
            return str(obj)


def _ensure_schema_version(spec: Dict[str, Any], target_version: str = "5.17.0") -> Dict[str, Any]:
    """
    Ensure the Vega-Lite specification has the correct $schema version.
    
    Args:
        spec: Vega-Lite specification dictionary
        target_version: Target Vega-Lite version (default: 6.1.0)
        
    Returns:
        Specification with ensured $schema field
    """
    if not isinstance(spec, dict):
        return spec
    
    # Ensure $schema is set to the target version
    spec["$schema"] = f"https://vega.github.io/schema/vega-lite/v{target_version}.json"
    return spec


class PlotGenerator:
    """Utility class for generating Vega-Lite plot specifications using Altair."""
    
    def __init__(self, plot_planning_agent: Optional[Any] = None):
        """
        Initialize the plot generator.
        
        Args:
            plot_planning_agent: Optional PlotPlanningAgent instance for intelligent plot configuration
        """
        self.plot_planning_agent = plot_planning_agent
    
    async def generate_plot(
        self,
        data: List[Dict[str, Any]],
        plot_type: str,
        question: str,
        columns: Optional[List[str]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Generate a Vega-Lite plot specification.
        
        Args:
            data: List of dictionaries representing the data rows
            plot_type: Type of plot ('bar', 'line', 'scatter', 'histogram')
            question: Original user question (for context)
            columns: Optional list of column names to use for the plot
        
        Returns:
            Vega-Lite JSON specification as a dictionary, or None if generation fails
        """
        logger.info(f"Starting plot generation: type={plot_type}, data_rows={len(data) if data else 0}, columns={columns}")
        
        if not data or len(data) == 0:
            logger.warning("Cannot generate plot: empty data")
            return None
        
        try:
            # Convert to DataFrame for easier manipulation
            df = pd.DataFrame(data)
            
            # Infer columns if not provided
            if columns is None or len(columns) == 0:
                columns = list(df.columns)
            
            # Filter to only existing columns
            columns = [col for col in columns if col in df.columns]
            
            if len(columns) == 0:
                logger.warning("No valid columns found for plot")
                return None
            
            # Infer column types
            col_types = self._infer_column_types(df, columns)
            
            # Use PlotPlanningAgent as primary method, regex only as fallback if agent unavailable or fails
            plot_config = None
            grouping_column = None
            
            if self.plot_planning_agent is not None:
                try:
                    # Call the agent to get plot configuration
                    agent_result = await self.plot_planning_agent.run(
                        question=question,
                        available_columns=columns,
                        column_types=col_types
                    )
                    plot_config = agent_result.output
                    logger.info(f"PlotPlanningAgent determined: {plot_config.reasoning}")
                    
                    # Use columns from config if provided, otherwise use original
                    if plot_config.columns:
                        # Filter to only existing columns
                        config_columns = [col for col in plot_config.columns if col in df.columns]
                        if config_columns:
                            columns = config_columns
                    
                    # Trust the agent's grouping_column decision completely (even if None)
                    grouping_column = plot_config.grouping_column
                except Exception as e:
                    logger.warning(f"PlotPlanningAgent failed, falling back to regex: {e}")
                    plot_config = None
            
            # Fallback to regex-based approach ONLY if agent is not available or failed
            if plot_config is None:
                logger.info("Using regex-based fallback for plot configuration")
                grouping_hint = None
                if question:
                    question_lower = question.lower()
                    # Look for explicit color/grouping patterns first (most specific)
                    # Pattern: "colored by X", "grouped by X", "color by X"
                    color_match = re.search(r'\b(colored|grouped|color)\s+by\s+(\w+)', question_lower)
                    if color_match:
                        grouping_hint = color_match.group(2)
                    else:
                        # Look for "for each X" or "for each X's" patterns
                        for_each_match = re.search(r'\bfor each\s+(\w+)(?:\'s|\')?', question_lower)
                        if for_each_match:
                            grouping_hint = for_each_match.group(1)
                        else:
                            # Look for "distributions of X for Y" pattern
                            dist_for_match = re.search(r'\bdistributions?\s+(?:of\s+)?\w+\s+for\s+(\w+)', question_lower)
                            if dist_for_match:
                                grouping_hint = dist_for_match.group(1)
                            else:
                                # Look for general grouping patterns: "by X", "across X", "per X"
                                by_match = re.search(r'\b(by|across|per)\s+(\w+)', question_lower)
                                if by_match:
                                    grouping_hint = by_match.group(2)
                
                if grouping_hint:
                    grouping_column = self._find_grouping_column(df, columns, grouping_hint, col_types)
            
            # Generate plot based on type
            plot_spec = None
            if plot_type == "bar":
                plot_spec = self._create_barplot(df, columns, grouping_column, plot_config)
            elif plot_type == "line":
                plot_spec = self._create_lineplot(df, columns, grouping_column, plot_config)
            elif plot_type == "scatter":
                plot_spec = self._create_scatterplot(df, columns, grouping_column, plot_config)
            elif plot_type == "histogram":
                plot_spec = self._create_histogram(df, columns, grouping_column, plot_config)
            else:
                logger.warning(f"Unknown plot type: {plot_type}")
                return None
            
            if plot_spec:
                logger.info(f"Successfully generated {plot_type} plot spec with keys: {list(plot_spec.keys()) if isinstance(plot_spec, dict) else 'N/A'}")
            else:
                logger.warning(f"Plot generation returned None for type: {plot_type}")
            
            return plot_spec
                
        except Exception as e:
            logger.error(f"Error generating plot: {e}", exc_info=True)
            return None
    
    def _infer_column_types(self, df: pd.DataFrame, columns: List[str]) -> Dict[str, str]:
        """
        Infer column types (numeric vs categorical).
        
        Args:
            df: DataFrame
            columns: List of column names
        
        Returns:
            Dictionary mapping column names to types ('quantitative' or 'nominal')
        """
        types = {}
        for col in columns:
            if col not in df.columns:
                continue
            
            # Check if column is numeric
            if pd.api.types.is_numeric_dtype(df[col]):
                types[col] = "quantitative"
            else:
                types[col] = "nominal"
        
        return types
    
    def _find_grouping_column(
        self, 
        df: pd.DataFrame, 
        columns: List[str], 
        grouping_hint: Optional[str] = None,
        col_types: Optional[Dict[str, str]] = None
    ) -> Optional[str]:
        """
        Find the appropriate categorical column to use for grouping/coloring.
        
        Args:
            df: DataFrame
            columns: List of column names to consider (for type inference, but we search all df columns)
            grouping_hint: Optional hint from question parsing (e.g., "species")
            col_types: Optional pre-computed column types dictionary
        
        Returns:
            Name of the grouping column, or None if none found
        """
        # Infer types for all columns in dataframe, not just the ones in columns list
        all_cols = list(df.columns)
        if col_types is None:
            col_types = self._infer_column_types(df, all_cols)
        else:
            # Ensure we have types for all columns in the dataframe
            for col in all_cols:
                if col not in col_types:
                    if pd.api.types.is_numeric_dtype(df[col]):
                        col_types[col] = "quantitative"
                    else:
                        col_types[col] = "nominal"
        
        # Search all categorical columns in the dataframe, not just those in columns list
        categorical_cols = [col for col in all_cols if col_types.get(col) == "nominal"]
        
        if not categorical_cols:
            return None
        
        # If we have a grouping hint, try to match it to a column
        if grouping_hint:
            hint_lower = grouping_hint.lower()
            # Try exact match first (case-insensitive)
            for cat_col in categorical_cols:
                if cat_col.lower() == hint_lower:
                    return cat_col
            
            # Try partial match (hint in column name or column name in hint)
            for cat_col in categorical_cols:
                if hint_lower in cat_col.lower() or cat_col.lower() in hint_lower:
                    return cat_col
        
        # If no hint or no match, use first categorical column
        return categorical_cols[0]
    
    def _create_barplot(self, df: pd.DataFrame, columns: List[str], grouping_column: Optional[str] = None, plot_config: Optional[PlotConfig] = None) -> Optional[Dict[str, Any]]:
        """Create a bar plot specification with optional color encoding."""
        try:
            col_types = self._infer_column_types(df, columns)
            
            # Use plot_config if available, otherwise infer
            if plot_config and plot_config.x_column:
                x_col = plot_config.x_column
            else:
                # Find categorical column for x-axis
                x_col = None
                for col in columns:
                    if col_types.get(col) == "nominal":
                        x_col = col
                        break
                
                # If no categorical, use first column
                if x_col is None:
                    x_col = columns[0]
            
            if plot_config and plot_config.y_column:
                y_col = plot_config.y_column
            else:
                # Find quantitative column for y-axis
                y_col = None
                for col in columns:
                    if col != x_col and col_types.get(col) == "quantitative":
                        y_col = col
                        break
            
            # Use grouping_column from parameter (set by generate_plot)
            group_col = grouping_column
            
            # Build encoding dictionary
            if y_col is None:
                encoding = {
                    "x": alt.X(x_col, type=col_types.get(x_col, "nominal")),
                    "y": alt.Y("count()", title="Count")
                }
            else:
                encoding = {
                    "x": alt.X(x_col, type=col_types.get(x_col, "nominal")),
                    "y": alt.Y(f"mean({y_col}):Q", title=f"Mean {y_col}")
                }
            
            # Add color encoding if we have a grouping column (different from x-axis)
            if group_col and group_col != x_col:
                unique_count = df[group_col].nunique()
                # Use color encoding for up to 10 categories
                if unique_count <= 10:
                    encoding["color"] = alt.Color(group_col, type="nominal", legend=alt.Legend(title=group_col))
            
            chart = alt.Chart(df).mark_bar().encode(**encoding).configure_axis(**PLOT_STYLE_CONFIG)
            
            spec = chart.to_dict()
            spec = _make_json_serializable(spec)
            spec = _ensure_schema_version(spec)
            return spec
            
        except Exception as e:
            logger.error(f"Error creating bar plot: {e}", exc_info=True)
            return None
    
    def _create_lineplot(self, df: pd.DataFrame, columns: List[str], grouping_column: Optional[str] = None, plot_config: Optional[PlotConfig] = None) -> Optional[Dict[str, Any]]:
        """Create a line plot specification with optional color encoding for multiple series."""
        try:
            col_types = self._infer_column_types(df, columns)
            
            # Use plot_config if available, otherwise infer
            if plot_config and plot_config.x_column:
                x_col = plot_config.x_column
            else:
                x_col = None
            
            if plot_config and plot_config.y_column:
                y_col = plot_config.y_column
            else:
                # Find quantitative column for y-axis
                y_col = None
                for col in columns:
                    if col_types.get(col) == "quantitative":
                        y_col = col
                        break
            
            # If not from config, find x-axis (prefer ordinal/numeric, but can use any)
            if x_col is None:
                for col in columns:
                    if col != y_col:
                        x_col = col
                        break
            
            if x_col is None or y_col is None:
                # Fallback: use first two columns
                if len(columns) >= 2:
                    x_col = columns[0]
                    y_col = columns[1]
                else:
                    logger.warning("Not enough columns for line plot")
                    return None
            
            # Use grouping_column from parameter (set by generate_plot)
            group_col = grouping_column
            
            # Build encoding dictionary
            encoding = {
                "x": alt.X(x_col, type=col_types.get(x_col, "quantitative")),
                "y": alt.Y(y_col, type="quantitative")
            }
            
            # Add color encoding if we have a grouping column
            if group_col:
                unique_count = df[group_col].nunique()
                # Use color encoding for up to 10 categories
                if unique_count <= 10:
                    encoding["color"] = alt.Color(group_col, type="nominal", legend=alt.Legend(title=group_col))
            
            chart = alt.Chart(df).mark_line().encode(**encoding).configure_axis(**PLOT_STYLE_CONFIG)
            
            spec = chart.to_dict()
            spec = _make_json_serializable(spec)
            spec = _ensure_schema_version(spec)
            return spec
            
        except Exception as e:
            logger.error(f"Error creating line plot: {e}", exc_info=True)
            return None
    
    def _create_scatterplot(self, df: pd.DataFrame, columns: List[str], grouping_column: Optional[str] = None, plot_config: Optional[PlotConfig] = None) -> Optional[Dict[str, Any]]:
        """Create a scatter plot specification with optional color encoding."""
        try:
            col_types = self._infer_column_types(df, columns)
            
            # Use plot_config if available, otherwise infer
            if plot_config and plot_config.x_column:
                x_col = plot_config.x_column
            else:
                x_col = None
            
            if plot_config and plot_config.y_column:
                y_col = plot_config.y_column
            else:
                # For scatter plots, need two quantitative columns
                quantitative_cols = [col for col in columns if col_types.get(col) == "quantitative"]
                
                if len(quantitative_cols) < 2:
                    # If not enough quantitative columns, use first two columns
                    if len(columns) >= 2:
                        x_col = columns[0]
                        y_col = columns[1]
                    else:
                        logger.warning("Not enough columns for scatter plot")
                        return None
                else:
                    x_col = quantitative_cols[0]
                    y_col = quantitative_cols[1]
            
            # Use grouping_column from parameter (set by generate_plot)
            group_col = grouping_column
            
            # Build encoding dictionary
            encoding = {
                "x": alt.X(x_col, type="quantitative"),
                "y": alt.Y(y_col, type="quantitative")
            }
            
            # Add color encoding if we have a grouping column
            if group_col:
                unique_count = df[group_col].nunique()
                # Use color encoding for up to 10 categories
                if unique_count <= 10:
                    encoding["color"] = alt.Color(group_col, type="nominal", legend=alt.Legend(title=group_col))
            
            chart = alt.Chart(df).mark_circle().encode(**encoding).configure_axis(**PLOT_STYLE_CONFIG)
            
            spec = chart.to_dict()
            spec = _make_json_serializable(spec)
            spec = _ensure_schema_version(spec)
            return spec
            
        except Exception as e:
            logger.error(f"Error creating scatter plot: {e}", exc_info=True)
            return None
    
    def _create_histogram(self, df: pd.DataFrame, columns: List[str], grouping_column: Optional[str] = None, plot_config: Optional[PlotConfig] = None) -> Optional[Dict[str, Any]]:
        """Create a histogram specification with support for grouping by categorical columns."""
        try:
            col_types = self._infer_column_types(df, columns)
            
            # Use plot_config if available, otherwise infer
            if plot_config and plot_config.x_column:
                col = plot_config.x_column
            else:
                # For histograms, need one quantitative column
                quantitative_cols = [col for col in columns if col_types.get(col) == "quantitative"]
                
                if len(quantitative_cols) == 0:
                    # If no quantitative column, use first column
                    if len(columns) > 0:
                        col = columns[0]
                    else:
                        logger.warning("No columns for histogram")
                        return None
                else:
                    col = quantitative_cols[0]
            
            # Use grouping_column from parameter (set by generate_plot)
            group_col = grouping_column
            
            # Verify grouping column exists in dataframe
            if group_col and group_col not in df.columns:
                logger.warning(f"Grouping column '{group_col}' not found in dataframe, ignoring grouping")
                group_col = None
            
            # If there's a categorical column, use it for grouping/color encoding
            # This allows comparing distributions across categories (e.g., species)
            if group_col:
                # Count unique values to decide between color encoding and faceting
                unique_count = df[group_col].nunique()
                
                if unique_count <= 5:
                    # Use color encoding for small number of categories
                    chart = alt.Chart(df).mark_bar(opacity=0.7).encode(
                        x=alt.X(col, type="quantitative", bin=True),
                        y=alt.Y("count()", title="Count"),
                        color=alt.Color(group_col, type="nominal", legend=alt.Legend(title=group_col))
                    )
                else:
                    # Use faceting for many categories
                    chart = alt.Chart(df).mark_bar().encode(
                        x=alt.X(col, type="quantitative", bin=True),
                        y=alt.Y("count()", title="Count")
                    ).facet(
                        column=alt.Column(group_col, type="nominal", header=alt.Header(title=group_col))
                    )
            else:
                # No grouping - simple histogram
                chart = alt.Chart(df).mark_bar().encode(
                    x=alt.X(col, type="quantitative", bin=True),
                    y=alt.Y("count()", title="Count")
                )
            
            spec = chart.to_dict()
            spec = _make_json_serializable(spec)
            spec = _ensure_schema_version(spec)
            return spec
            
        except Exception as e:
            logger.error(f"Error creating histogram: {e}", exc_info=True)
            return None

