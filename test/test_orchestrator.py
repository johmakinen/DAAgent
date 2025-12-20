import pytest
from app.agents.orchestrator import OrchestratorAgent

@pytest.mark.asyncio
async def test_orchestrator_agent_init():
    agent = OrchestratorAgent(model='azure:gpt-5-nano')
    assert agent is not None
    assert hasattr(agent, "planner_agent")
    assert hasattr(agent, "database_query_agent")
    assert hasattr(agent, "synthesizer_agent")
