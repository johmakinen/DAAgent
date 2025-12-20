"""Pydantic models for typed inputs and outputs between agents and users."""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class UserMessage(BaseModel):
    """User input message model."""
    content: str = Field(..., description="The user's message content")
    session_id: Optional[str] = Field(None, description="Optional session identifier")


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

