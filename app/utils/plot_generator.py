"""Plot generation utility using Plotly to create interactive charts."""
import logging
import re
import json
from typing import Optional, List, Dict, Any
import pandas as pd
import plotly.graph_objects as go
from app.core.models import PlotConfig

logger = logging.getLogger(__name__)

# Executive-friendly color palette (professional blues, grays, muted colors)
EXECUTIVE_COLORS = [
    '#1f77b4',  # Blue
    '#2ca02c',  # Green
    '#d62728',  # Red
    '#ff7f0e',  # Orange
    '#9467bd',  # Purple
    '#8c564b',  # Brown
    '#e377c2',  # Pink
    '#7f7f7f',  # Gray
    '#bcbd22',  # Olive
    '#17becf',  # Cyan
]

def _get_executive_layout(title: Optional[str] = None, xaxis_title: Optional[str] = None, yaxis_title: Optional[str] = None) -> Dict[str, Any]:
    """
    Get executive-friendly layout configuration for Plotly charts.
    
    Args:
        title: Chart title
        xaxis_title: X-axis title
        yaxis_title: Y-axis title
    
    Returns:
        Layout dictionary with professional styling
    """
    layout = {
        "title": {
            "text": title or "",
            "font": {
                "size": 20,
                "family": "Arial, sans-serif",
                "color": "#2c3e50"
            },
            "x": 0.5,
            "xanchor": "center"
        },
        "font": {
            "family": "Arial, sans-serif",
            "size": 14,
            "color": "#2c3e50"
        },
        "plot_bgcolor": "white",
        "paper_bgcolor": "white",
        "margin": {
            "l": 80,
            "r": 50,
            "t": 80,
            "b": 80
        },
        "xaxis": {
            "title": {
                "text": xaxis_title or "",
                "font": {
                    "size": 16,
                    "family": "Arial, sans-serif",
                    "color": "#2c3e50"
                }
            },
            "showgrid": True,
            "gridcolor": "#e0e0e0",
            "gridwidth": 1,
            "zeroline": False,
            "linecolor": "#b0b0b0",
            "linewidth": 1
        },
        "yaxis": {
            "title": {
                "text": yaxis_title or "",
                "font": {
                    "size": 16,
                    "family": "Arial, sans-serif",
                    "color": "#2c3e50"
                }
            },
            "showgrid": True,
            "gridcolor": "#e0e0e0",
            "gridwidth": 1,
            "zeroline": False,
            "linecolor": "#b0b0b0",
            "linewidth": 1
        },
        "legend": {
            "font": {
                "size": 14,
                "family": "Arial, sans-serif",
                "color": "#2c3e50"
            },
            "bgcolor": "rgba(255, 255, 255, 0.8)",
            "bordercolor": "#e0e0e0",
            "borderwidth": 1
        },
        "hovermode": "closest",
        "width": 800,
        "height": 500
    }
    return layout


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
    # Handle numpy arrays first (they have both tolist and item, but item only works for scalars)
    elif hasattr(obj, 'tolist'):
        return _make_json_serializable(obj.tolist())
    # Handle numpy scalar types (0-dimensional arrays)
    elif hasattr(obj, 'item') and hasattr(obj, 'ndim') and obj.ndim == 0:
        return obj.item()
    elif hasattr(obj, 'item'):  # Other types with item() method (but not arrays)
        try:
            return obj.item()
        except (ValueError, AttributeError):
            # If item() fails, try tolist or convert to string
            if hasattr(obj, 'tolist'):
                return _make_json_serializable(obj.tolist())
            return str(obj)
    else:
        # For other types, try to convert to string or use JSON serialization
        try:
            # Test if it's already JSON-serializable
            json.dumps(obj)
            return obj
        except (TypeError, ValueError):
            # If it can't be serialized, convert to string representation
            return str(obj)


class PlotGenerator:
    """Utility class for generating Plotly charts with executive-friendly styling."""
    
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
        Generate a Plotly figure dictionary.
        
        Args:
            data: List of dictionaries representing the data rows
            plot_type: Type of plot ('bar', 'line', 'scatter', 'histogram')
            question: Original user question (for context)
            columns: Optional list of column names to use for the plot
        
        Returns:
            Plotly figure dictionary (with 'data' and 'layout' keys), or None if generation fails
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
            fig = None
            if plot_type == "bar":
                fig = self._create_barplot(df, columns, grouping_column, plot_config, question)
            elif plot_type == "line":
                fig = self._create_lineplot(df, columns, grouping_column, plot_config, question)
            elif plot_type == "scatter":
                fig = self._create_scatterplot(df, columns, grouping_column, plot_config, question)
            elif plot_type == "histogram":
                fig = self._create_histogram(df, columns, grouping_column, plot_config, question)
            else:
                logger.warning(f"Unknown plot type: {plot_type}")
                return None
            
            if fig:
                # Convert Plotly figure to dictionary
                fig_dict = fig.to_dict()
                # Make it JSON-serializable
                fig_dict = _make_json_serializable(fig_dict)
                logger.info(f"Successfully generated {plot_type} plot with {len(fig_dict.get('data', []))} traces")
                return fig_dict
            else:
                logger.warning(f"Plot generation returned None for type: {plot_type}")
                return None
                
        except Exception as e:
            logger.error(f"Error generating plot: {e}", exc_info=True)
            return None
    
    @staticmethod
    def extract_plot_metadata(plot_spec_dict: Dict[str, Any], plot_type: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Extract key metadata from a Plotly figure dictionary.
        
        Args:
            plot_spec_dict: Plotly figure dictionary (from fig.to_dict())
            plot_type: Original plot type used to generate the plot ('bar', 'line', 'scatter', 'histogram')
                      If provided, this takes precedence over trace type inference
            
        Returns:
            Dictionary with plot metadata, or None if extraction fails
        """
        try:
            metadata = {
                "plot_type": None,
                "x_axis_label": None,
                "y_axis_label": None,
                "title": None,
                "bin_width": None,
                "bin_start": None,
                "bin_end": None,
                "num_bins": None,
                "grouping_column": None,
                "groups": None
            }
            
            # Extract layout information
            layout = plot_spec_dict.get("layout", {})
            
            # Extract title
            title_info = layout.get("title", {})
            if isinstance(title_info, dict):
                metadata["title"] = title_info.get("text", "")
            elif isinstance(title_info, str):
                metadata["title"] = title_info
            
            # Extract axis labels
            xaxis = layout.get("xaxis", {})
            yaxis = layout.get("yaxis", {})
            
            xaxis_title = xaxis.get("title", {})
            if isinstance(xaxis_title, dict):
                metadata["x_axis_label"] = xaxis_title.get("text", "")
            elif isinstance(xaxis_title, str):
                metadata["x_axis_label"] = xaxis_title
            
            yaxis_title = yaxis.get("title", {})
            if isinstance(yaxis_title, dict):
                metadata["y_axis_label"] = yaxis_title.get("text", "")
            elif isinstance(yaxis_title, str):
                metadata["y_axis_label"] = yaxis_title
            
            # Extract data traces
            data = plot_spec_dict.get("data", [])
            if not data:
                return metadata
            
            # Extract trace information for use in both plot type determination and metadata extraction
            first_trace = data[0]
            trace_type = first_trace.get("type", "")
            mode = first_trace.get("mode", "")
            
            # Determine plot type - use provided plot_type if available, otherwise infer from trace
            if plot_type:
                metadata["plot_type"] = plot_type
            else:
                # Infer from trace type (but note: line plots use Scatter traces)
                # Map Plotly trace types to our plot types
                if trace_type == "histogram":
                    metadata["plot_type"] = "histogram"
                elif trace_type == "bar":
                    metadata["plot_type"] = "bar"
                elif trace_type == "scatter":
                    # Distinguish between line plots (lines+markers) and scatter plots (markers only)
                    if "lines" in mode or "line" in mode:
                        metadata["plot_type"] = "line"
                    else:
                        metadata["plot_type"] = "scatter"
                else:
                    metadata["plot_type"] = trace_type
            
            # Extract histogram-specific metadata
            if trace_type == "histogram":
                xbins = first_trace.get("xbins", {})
                if isinstance(xbins, dict):
                    metadata["bin_start"] = xbins.get("start")
                    metadata["bin_end"] = xbins.get("end")
                    bin_size = xbins.get("size")
                    if bin_size is not None:
                        metadata["bin_width"] = bin_size
                    else:
                        # Calculate bin width from start, end, and nbinsx if available
                        nbinsx = first_trace.get("nbinsx")
                        if nbinsx and metadata["bin_start"] is not None and metadata["bin_end"] is not None:
                            metadata["num_bins"] = nbinsx
                            if nbinsx > 0:
                                metadata["bin_width"] = (metadata["bin_end"] - metadata["bin_start"]) / nbinsx
                        elif metadata["bin_start"] is not None and metadata["bin_end"] is not None:
                            # Try to infer from data range
                            x_data = first_trace.get("x", [])
                            if x_data:
                                import numpy as np
                                if hasattr(x_data, '__iter__') and not isinstance(x_data, str):
                                    x_array = np.array(list(x_data))
                                    if len(x_array) > 0:
                                        data_min = float(np.min(x_array))
                                        data_max = float(np.max(x_array))
                                        nbinsx = first_trace.get("nbinsx", 30)
                                        if nbinsx > 0:
                                            metadata["bin_width"] = (data_max - data_min) / nbinsx
                                            metadata["num_bins"] = nbinsx
            
            # Extract grouping information (if multiple traces with names)
            if len(data) > 1:
                # Check if traces have names (indicating grouping)
                trace_names = [trace.get("name") for trace in data if trace.get("name")]
                if trace_names:
                    metadata["groups"] = trace_names
                    # Try to infer grouping column from legend or trace metadata
                    # This is best-effort since Plotly doesn't always store this
                    legend = layout.get("legend", {})
                    if legend:
                        metadata["grouping_column"] = "grouped"  # Generic indicator
            
            return metadata
            
        except Exception as e:
            logger.warning(f"Failed to extract plot metadata: {e}", exc_info=True)
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
    
    def _infer_label_from_question(self, column_name: str, question: str, axis: str = "y") -> str:
        """
        Infer a human-readable label from the question and column name.
        
        Args:
            column_name: The column name to create a label for
            question: The user's question
            axis: 'x' or 'y' to help infer context
        
        Returns:
            Human-readable label
        """
        question_lower = question.lower()
        col_lower = column_name.lower()
        
        # Common mappings
        label_mappings = {
            'year': 'Year',
            'time': 'Time',
            'date': 'Date',
            'income': 'Income',
            'population': 'Population',
            'price': 'Price',
            'value': None,  # Will infer from question context
            'count': 'Count',
            'amount': 'Amount',
            'size': 'Size',
            'area': 'Area',
            'postal_code': 'Postal Code',
            'postal_code_area': 'Postal Code Area',
        }
        
        # Check direct mappings first
        for key, label in label_mappings.items():
            if key in col_lower:
                if label:
                    return label
        
        # For generic 'value' column, try to infer from question
        if 'value' in col_lower:
            if 'income' in question_lower:
                return 'Income'
            elif 'population' in question_lower:
                return 'Population'
            elif 'price' in question_lower:
                return 'Price'
            elif 'amount' in question_lower:
                return 'Amount'
            # Default for value
            return 'Value'
        
        # For time-related columns
        if any(term in col_lower for term in ['year', 'time', 'date', 'month', 'day']):
            return 'Year' if 'year' in col_lower else 'Time'
        
        # Capitalize and format column name as fallback
        return column_name.replace('_', ' ').title()
    
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
    
    def _create_barplot(self, df: pd.DataFrame, columns: List[str], grouping_column: Optional[str] = None, plot_config: Optional[PlotConfig] = None, question: str = "") -> Optional[go.Figure]:
        """Create a bar plot with optional color encoding."""
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
            
            # Determine labels: use plot_config labels if available, otherwise infer from question
            x_label = None
            y_label = None
            plot_title = None
            
            if plot_config:
                x_label = plot_config.x_label
                y_label = plot_config.y_label
                plot_title = plot_config.title
            
            # Determine y-axis values
            if y_col is None:
                # Count by x_col
                y_values = df.groupby(x_col).size().reset_index(name='count')
                y_col_name = 'count'
                if not y_label:
                    y_label = "Count"
            else:
                # Aggregate by x_col
                if group_col and group_col != x_col:
                    y_values = df.groupby([x_col, group_col])[y_col].mean().reset_index()
                    y_col_name = y_col
                    if not y_label:
                        y_label = self._infer_label_from_question(y_col, question, axis="y")
                else:
                    y_values = df.groupby(x_col)[y_col].mean().reset_index()
                    y_col_name = y_col
                    if not y_label:
                        y_label = self._infer_label_from_question(y_col, question, axis="y")
            
            # Fallback to inference if labels not provided
            if not x_label:
                x_label = self._infer_label_from_question(x_col, question, axis="x")
            if not plot_title:
                plot_title = f"{y_label} by {x_label}"
            
            # Create figure
            if group_col and group_col != x_col and y_values[group_col].nunique() <= 10:
                # Use color grouping
                fig = go.Figure()
                unique_groups = sorted(y_values[group_col].unique())
                for i, group_val in enumerate(unique_groups):
                    group_data = y_values[y_values[group_col] == group_val]
                    fig.add_trace(go.Bar(
                        x=group_data[x_col],
                        y=group_data[y_col_name],
                        name=str(group_val),
                        marker_color=EXECUTIVE_COLORS[i % len(EXECUTIVE_COLORS)],
                        hovertemplate=f'<b>{group_col}: {group_val}</b><br>{x_label}: %{{x}}<br>{y_label}: %{{y}}<extra></extra>'
                    ))
                layout = _get_executive_layout(
                    title=plot_title,
                    xaxis_title=x_label,
                    yaxis_title=y_label
                )
                fig.update_layout(**layout)
            else:
                # Simple bar chart
                fig = go.Figure(data=[
                    go.Bar(
                        x=y_values[x_col],
                        y=y_values[y_col_name],
                        marker_color=EXECUTIVE_COLORS[0],
                        hovertemplate=f'<b>{x_label}: %{{x}}</b><br>{y_label}: %{{y}}<extra></extra>'
                    )
                ])
                layout = _get_executive_layout(
                    title=plot_title,
                    xaxis_title=x_label,
                    yaxis_title=y_label
                )
                fig.update_layout(**layout)
            
            return fig
            
        except Exception as e:
            logger.error(f"Error creating bar plot: {e}", exc_info=True)
            return None
    
    def _create_lineplot(self, df: pd.DataFrame, columns: List[str], grouping_column: Optional[str] = None, plot_config: Optional[PlotConfig] = None, question: str = "") -> Optional[go.Figure]:
        """Create a line plot with optional color encoding for multiple series."""
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
            
            # Determine labels: use plot_config labels if available, otherwise infer from question
            x_label = None
            y_label = None
            plot_title = None
            
            if plot_config:
                x_label = plot_config.x_label
                y_label = plot_config.y_label
                plot_title = plot_config.title
            
            # Fallback to inference if labels not provided
            if not x_label:
                x_label = self._infer_label_from_question(x_col, question, axis="x")
            if not y_label:
                y_label = self._infer_label_from_question(y_col, question, axis="y")
            if not plot_title:
                plot_title = f"{y_label} over {x_label}"
            
            # Use grouping_column from parameter (set by generate_plot)
            group_col = grouping_column
            
            # Create figure
            fig = go.Figure()
            
            if group_col and df[group_col].nunique() <= 10:
                # Multiple lines by group
                unique_groups = sorted(df[group_col].unique())
                for i, group_val in enumerate(unique_groups):
                    group_data = df[df[group_col] == group_val].sort_values(x_col)
                    fig.add_trace(go.Scatter(
                        x=group_data[x_col],
                        y=group_data[y_col],
                        mode='lines+markers',
                        name=str(group_val),
                        line=dict(color=EXECUTIVE_COLORS[i % len(EXECUTIVE_COLORS)], width=2.5),
                        marker=dict(size=6),
                        hovertemplate=f'<b>{group_col}: {group_val}</b><br>{x_label}: %{{x}}<br>{y_label}: %{{y}}<extra></extra>'
                    ))
                layout = _get_executive_layout(
                    title=plot_title,
                    xaxis_title=x_label,
                    yaxis_title=y_label
                )
                fig.update_layout(**layout)
            else:
                # Single line
                sorted_df = df.sort_values(x_col)
                fig.add_trace(go.Scatter(
                    x=sorted_df[x_col],
                    y=sorted_df[y_col],
                    mode='lines+markers',
                    line=dict(color=EXECUTIVE_COLORS[0], width=2.5),
                    marker=dict(size=6),
                    hovertemplate=f'<b>{x_label}: %{{x}}</b><br>{y_label}: %{{y}}<extra></extra>'
                ))
                layout = _get_executive_layout(
                    title=plot_title,
                    xaxis_title=x_label,
                    yaxis_title=y_label
                )
                fig.update_layout(**layout)
            
            return fig
            
        except Exception as e:
            logger.error(f"Error creating line plot: {e}", exc_info=True)
            return None
    
    def _create_scatterplot(self, df: pd.DataFrame, columns: List[str], grouping_column: Optional[str] = None, plot_config: Optional[PlotConfig] = None, question: str = "") -> Optional[go.Figure]:
        """Create a scatter plot with optional color encoding."""
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
            
            # Determine labels: use plot_config labels if available, otherwise infer from question
            x_label = None
            y_label = None
            plot_title = None
            
            if plot_config:
                x_label = plot_config.x_label
                y_label = plot_config.y_label
                plot_title = plot_config.title
            
            # Fallback to inference if labels not provided
            if not x_label:
                x_label = self._infer_label_from_question(x_col, question, axis="x")
            if not y_label:
                y_label = self._infer_label_from_question(y_col, question, axis="y")
            if not plot_title:
                plot_title = f"{y_label} vs {x_label}"
            
            # Create figure
            fig = go.Figure()
            
            if group_col and df[group_col].nunique() <= 10:
                # Multiple scatter traces by group
                unique_groups = sorted(df[group_col].unique())
                for i, group_val in enumerate(unique_groups):
                    group_data = df[df[group_col] == group_val]
                    fig.add_trace(go.Scatter(
                        x=group_data[x_col],
                        y=group_data[y_col],
                        mode='markers',
                        name=str(group_val),
                        marker=dict(
                            color=EXECUTIVE_COLORS[i % len(EXECUTIVE_COLORS)],
                            size=8,
                            opacity=0.7
                        ),
                        hovertemplate=f'<b>{group_col}: {group_val}</b><br>{x_label}: %{{x}}<br>{y_label}: %{{y}}<extra></extra>'
                    ))
                layout = _get_executive_layout(
                    title=plot_title,
                    xaxis_title=x_label,
                    yaxis_title=y_label
                )
                fig.update_layout(**layout)
            else:
                # Single scatter trace
                fig.add_trace(go.Scatter(
                    x=df[x_col],
                    y=df[y_col],
                    mode='markers',
                    marker=dict(
                        color=EXECUTIVE_COLORS[0],
                        size=8,
                        opacity=0.7
                    ),
                    hovertemplate=f'<b>{x_label}: %{{x}}</b><br>{y_label}: %{{y}}<extra></extra>'
                ))
                layout = _get_executive_layout(
                    title=plot_title,
                    xaxis_title=x_label,
                    yaxis_title=y_label
                )
                fig.update_layout(**layout)
            
            return fig
            
        except Exception as e:
            logger.error(f"Error creating scatter plot: {e}", exc_info=True)
            return None
    
    def _create_histogram(self, df: pd.DataFrame, columns: List[str], grouping_column: Optional[str] = None, plot_config: Optional[PlotConfig] = None, question: str = "") -> Optional[go.Figure]:
        """Create a histogram with support for grouping by categorical columns."""
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
            
            # Determine labels: use plot_config labels if available, otherwise infer from question
            x_label = None
            y_label = "Count"
            plot_title = None
            
            if plot_config:
                x_label = plot_config.x_label
                if plot_config.y_label:
                    y_label = plot_config.y_label
                plot_title = plot_config.title
            
            # Fallback to inference if labels not provided
            if not x_label:
                x_label = self._infer_label_from_question(col, question, axis="x")
            if not plot_title:
                plot_title = f"Distribution of {x_label}"
            
            # Create figure
            fig = go.Figure()
            
            if group_col and df[group_col].nunique() <= 5:
                # Overlaid histograms by group
                unique_groups = sorted(df[group_col].unique())
                for i, group_val in enumerate(unique_groups):
                    group_data = df[df[group_col] == group_val]
                    fig.add_trace(go.Histogram(
                        x=group_data[col],
                        name=str(group_val),
                        opacity=0.7,
                        marker_color=EXECUTIVE_COLORS[i % len(EXECUTIVE_COLORS)],
                        hovertemplate=f'<b>{group_col}: {group_val}</b><br>{x_label}: %{{x}}<br>{y_label}: %{{y}}<extra></extra>'
                    ))
                layout = _get_executive_layout(
                    title=plot_title,
                    xaxis_title=x_label,
                    yaxis_title=y_label
                )
                fig.update_layout(**layout, barmode='overlay')
            else:
                # Simple histogram
                fig.add_trace(go.Histogram(
                    x=df[col],
                    marker_color=EXECUTIVE_COLORS[0],
                    hovertemplate=f'<b>{x_label}: %{{x}}</b><br>{y_label}: %{{y}}<extra></extra>'
                ))
                layout = _get_executive_layout(
                    title=plot_title,
                    xaxis_title=x_label,
                    yaxis_title=y_label
                )
                fig.update_layout(**layout)
            
            return fig
            
        except Exception as e:
            logger.error(f"Error creating histogram: {e}", exc_info=True)
            return None
