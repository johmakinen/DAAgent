"""Common dependency types for agents."""
from pydantic import BaseModel


class EmptyDeps(BaseModel):
    """Empty dependencies for agents that don't need any dependencies."""
    pass
