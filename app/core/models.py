"""Pydantic models for typed inputs and outputs between agents and users."""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class UserMessage(BaseModel):
    """User input message model."""
    content: str = Field(..., description="The user's message content")
    session_id: Optional[str] = Field(None, description="Optional session identifier")
    username: Optional[str] = Field(None, description="Optional username for tracing")


class PlotSpec(BaseModel):
    """Plotly figure specification model."""
    spec: Dict[str, Any] = Field(..., description="Plotly figure dictionary with 'data' and 'layout' keys")
    plot_type: str = Field(..., description="Type of plot: 'bar', 'line', 'scatter', or 'histogram'")


class PlotConfig(BaseModel):
    """Plot configuration determined by PlotPlanningAgent."""
    plot_type: str = Field(..., description="Type of plot: 'bar', 'line', 'scatter', or 'histogram'")
    x_column: Optional[str] = Field(None, description="Column name for x-axis")
    y_column: Optional[str] = Field(None, description="Column name for y-axis")
    grouping_column: Optional[str] = Field(None, description="Column name to use for grouping/color encoding")
    columns: Optional[List[str]] = Field(None, description="List of columns to include in the plot")
    reasoning: str = Field(..., description="Brief reasoning for the plot configuration")


class SynthesizerOutput(BaseModel):
    """Output from SynthesizerAgent including plot decision."""
    message: str = Field(..., description="The agent's response message")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Confidence score if applicable")
    requires_followup: bool = Field(False, description="Whether the response requires user followup")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    should_generate_plot: bool = Field(False, description="Whether a plot should be generated (only for database queries)")
    plot_type: Optional[str] = Field(None, description="Type of plot if needed: 'bar', 'line', 'scatter', or 'histogram'")
    plot_columns: Optional[List[str]] = Field(None, description="Column names to use for the plot")


class AgentResponse(BaseModel):
    """Final agent response model with structured output."""
    message: str = Field(..., description="The agent's response message")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Confidence score if applicable")
    requires_followup: bool = Field(False, description="Whether the response requires user followup")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")
    plot_spec: Optional[PlotSpec] = Field(None, description="Optional Plotly figure specification")


class IntentClassification(BaseModel):
    """Intent classification output from IntentAgent. (Deprecated: Use ExecutionPlan instead)"""
    intent_type: str = Field(..., description="Type of intent: 'database_query' or 'general_question'")
    requires_clarification: bool = Field(False, description="Whether clarification is needed from the user")
    clarification_question: Optional[str] = Field(None, description="Question to ask user if clarification needed")
    reasoning: str = Field(..., description="Brief reasoning for the intent classification")


class ExecutionPlan(BaseModel):
    """Execution plan created by PlannerAgent."""
    intent_type: str = Field(..., description="Type of intent: 'database_query' or 'general_question'")
    requires_clarification: bool = Field(False, description="Whether clarification is needed from the user")
    clarification_question: Optional[str] = Field(None, description="Question to ask user if clarification needed")
    reasoning: str = Field(..., description="Brief reasoning for the plan")
    requires_plot: bool = Field(False, description="Whether a plot is needed for the answer")
    plot_type: Optional[str] = Field(None, description="Type of plot if needed: 'bar', 'line', 'scatter', or 'histogram'")
    use_cached_data: bool = Field(False, description="Whether to use cached data instead of new query")
    cached_data_key: Optional[str] = Field(None, description="Key to identify which cached data to use (e.g., 'latest' or specific identifier)")
    sql_query: Optional[str] = Field(None, description="DEPRECATED: Do not populate this field. SQL generation is handled by DatabaseQueryAgent, not the planner.")
    explanation: str = Field(..., description="Brief explanation of the execution plan")


class DatabaseQuery(BaseModel):
    """Database query model for SQL operations."""
    query: str = Field(..., description="SQL query to execute")
    parameters: Optional[Dict[str, Any]] = Field(None, description="Query parameters if needed")


class DatabaseResult(BaseModel):
    """Database query result model."""
    success: bool = Field(..., description="Whether the query executed successfully")
    data: Optional[List[Dict[str, Any]]] = Field(None, description="Query results as list of dictionaries")
    error: Optional[str] = Field(None, description="Error message if query failed")
    row_count: int = Field(0, description="Number of rows returned")


class QueryAgentOutput(BaseModel):
    """Output from DatabaseQueryAgent after generating and executing query."""
    sql_query: str = Field(..., description="The SQL query that was generated and executed")
    query_result: DatabaseResult = Field(..., description="Result from executing the query")
    explanation: str = Field(..., description="Brief explanation of what the query does")
    requires_clarification: bool = Field(False, description="Whether clarification is needed from the user after max retries")
    clarification_question: Optional[str] = Field(None, description="Question to ask user if clarification needed (e.g., 'Do you mean X or Y? Both are in the table Z')")


class ToolCall(BaseModel):
    """Represents a tool invocation in the execution trace."""
    tool_name: str = Field(..., description="Name of the tool that was called")
    inputs: Dict[str, Any] = Field(..., description="Input arguments passed to the tool")
    outputs: Optional[Dict[str, Any]] = Field(None, description="Output/result from the tool execution")
    duration_ms: Optional[float] = Field(None, description="Duration of tool execution in milliseconds")
    error: Optional[str] = Field(None, description="Error message if tool execution failed")


class ColumnInfo(BaseModel):
    """Information about a database column."""
    name: str = Field(..., description="Column name")
    type: str = Field(..., description="SQL data type")
    description: str = Field(..., description="What the column represents")
    example_values: Optional[List[str]] = Field(None, description="Optional example values for this column")


class TableInfo(BaseModel):
    """Information about a database table."""
    name: str = Field(..., description="Table name")
    description: str = Field(..., description="What the table represents")
    columns: List[ColumnInfo] = Field(..., description="List of columns in this table")
    example_queries: Optional[List[str]] = Field(None, description="Example query patterns for this table")


class JoinColumn(BaseModel):
    """Information about a join column between tables."""
    from_column: str = Field(..., description="Column name in the from_table")
    to_column: str = Field(..., description="Column name in the to_table")
    description: Optional[str] = Field(None, description="Description of the join column")


class TableRelationship(BaseModel):
    """Information about a relationship between two tables."""
    from_table: str = Field(..., description="Source table name")
    to_table: str = Field(..., description="Target table name")
    type: str = Field(..., description="Relationship type (e.g., 'many-to-many', 'one-to-many')")
    description: str = Field(..., description="Description of the relationship")
    join_columns: List[JoinColumn] = Field(..., description="Columns used to join the tables")
    example_queries: Optional[List[str]] = Field(None, description="Example queries using this relationship")


class DatabasePack(BaseModel):
    """Database pack containing semantic information about the database schema."""
    name: str = Field(..., description="Database name")
    description: str = Field(..., description="Overall database description")
    tables: List[TableInfo] = Field(..., description="List of tables in the database")
    relationships: Optional[List[TableRelationship]] = Field(None, description="Relationships between tables")

