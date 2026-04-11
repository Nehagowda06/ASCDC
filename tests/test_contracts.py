from core.agents.smart_agent import SmartAgent
from env.environment import ASCDCEnvironment


def test_agent_env_contract():
    env = ASCDCEnvironment(seed=42)
    agent = SmartAgent()

    action = agent.act(env)

    assert isinstance(action, dict)
    assert "type" in action
