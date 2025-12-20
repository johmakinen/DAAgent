"""Pydantic models for typed inputs and outputs between agents and users."""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class UserMessage(BaseModel):
    """User input message model."""
    content: str = Field(..., description="The user's message content")
    session_id: Optional[str] = Field(None, description="Optional session identifier")
    username: Optional[str] = Field(None, description="Optional username for tracing")


class AgentResponse(BaseModel):
    """Final agent response model with structured output."""
    message: str = Field(..., description="The agent's response message")
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0, description="Confidence score if applicable")
    requires_followup: bool = Field(False, description="Whether the response requires user followup")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class IntentClassification(BaseModel):
    """Intent classification output from IntentAgent."""
    intent_type: str = Field(..., description="Type of intent: 'database_query' or 'general_question'")
    requires_clarification: bool = Field(False, description="Whether clarification is needed from the user")
    clarification_question: Optional[str] = Field(None, description="Question to ask user if clarification needed")
    reasoning: str = Field(..., description="Brief reasoning for the intent classification")


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


class GeneralAnswerOutput(BaseModel):
    """Output from GeneralAnswerAgent."""
    answer: str = Field(..., description="The general answer to the user's question")
    sources: Optional[List[str]] = Field(None, description="Optional sources or references used")


class ToolCall(BaseModel):
    """Represents a tool invocation in the execution trace."""
    tool_name: str = Field(..., description="Name of the tool that was called")
    inputs: Dict[str, Any] = Field(..., description="Input arguments passed to the tool")
    outputs: Optional[Dict[str, Any]] = Field(None, description="Output/result from the tool execution")
    duration_ms: Optional[float] = Field(None, description="Duration of tool execution in milliseconds")
    error: Optional[str] = Field(None, description="Error message if tool execution failed")


class AgentStep(BaseModel):
    """Represents a single agent execution step in the execution trace."""
    agent_name: str = Field(..., description="Name of the agent (e.g., 'intent-agent', 'database-query-agent')")
    step_order: int = Field(..., description="Order of this step in the execution flow")
    inputs: Dict[str, Any] = Field(..., description="Inputs to the agent")
    outputs: Optional[Dict[str, Any]] = Field(None, description="Outputs from the agent")
    tool_calls: List[ToolCall] = Field(default_factory=list, description="Tool calls made during this step")
    duration_ms: Optional[float] = Field(None, description="Duration of agent execution in milliseconds")
    reasoning: Optional[str] = Field(None, description="Reasoning or explanation if available")


class ExecutionTrace(BaseModel):
    """Complete execution trace of the orchestration flow."""
    trace_id: Optional[str] = Field(None, description="MLflow trace ID")
    steps: List[AgentStep] = Field(default_factory=list, description="List of agent execution steps in order")
    total_duration_ms: Optional[float] = Field(None, description="Total execution duration in milliseconds")


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


class DatabasePack(BaseModel):
    """Database pack containing semantic information about the database schema."""
    name: str = Field(..., description="Database name")
    description: str = Field(..., description="Overall database description")
    tables: List[TableInfo] = Field(..., description="List of tables in the database")

