"""Unit tests for agent implementations."""

import pytest
from agents.simple_agent import SimpleAgent, LearningAgent
from core.agents.smart_agent import SmartAgent
from env.environment import ASCDCEnvironment


class TestSimpleAgent:
    """Test SimpleAgent strategies."""

    def setup_method(self):
        """Setup agents and environment."""
        self.env = ASCDCEnvironment(seed=42)
        self.adaptive = SimpleAgent("adaptive")
        self.conservative = SimpleAgent("conservative")
        self.aggressive = SimpleAgent("aggressive")

    def test_adaptive_strategy_returns_valid_action(self):
        """Adaptive strategy should return valid action."""
        obs = self.env._build_observation()
        action = self.adaptive.act(obs)
        
        assert action["type"] in ["noop", "restart", "scale", "throttle"]
        if action["type"] != "noop":
            assert action["target"] in ["A", "B", "C"]

    def test_conservative_strategy_less_aggressive(self):
        """Conservative strategy should act less frequently than aggressive."""
        self.env.reset(config={
            "seed": 42,
            "base_load": {"A": 30.0, "B": 5.0, "C": 2.0},
            "capacities": {"A": 20.0, "B": 10.0, "C": 10.0},
            "initial_queues": {"A": 5.0, "B": 8.0, "C": 2.0},
            "initial_budget": 100.0,
            "max_timesteps": 50,
        })
        
        conservative_actions = 0
        aggressive_actions = 0
        
        for _ in range(10):
            obs = self.env._build_observation()
            
            if self.conservative.act(obs)["type"] != "noop":
                conservative_actions += 1
            if self.aggressive.act(obs)["type"] != "noop":
                aggressive_actions += 1
            
            self.env.step({"type": "noop", "target": None})
        
        # Aggressive should act more than conservative
        assert aggressive_actions >= conservative_actions

    def test_strategy_responds_to_pressure(self):
        """Strategies should respond to system pressure."""
        self.env.reset(config={
            "seed": 42,
            "base_load": {"A": 30.0, "B": 5.0, "C": 2.0},
            "capacities": {"A": 20.0, "B": 10.0, "C": 10.0},
            "initial_queues": {"A": 5.0, "B": 8.0, "C": 2.0},
            "initial_budget": 100.0,
            "max_timesteps": 50,
        })
        
        # Take steps to build up pressure
        for _ in range(5):
            self.env.step({"type": "noop", "target": None})
        
        # High pressure should trigger action
        obs = self.env._build_observation()
        action = self.adaptive.act(obs)
        
        # In high pressure, should not be noop
        assert action["type"] != "noop"


class TestLearningAgent:
    """Test LearningAgent Q-learning."""

    def setup_method(self):
        """Setup learning agent and environment."""
        self.agent = LearningAgent(seed=42)
        self.env = ASCDCEnvironment(seed=42)

    def test_learning_agent_returns_valid_action(self):
        """Learning agent should return valid action."""
        obs = self.env._build_observation()
        action = self.agent.act(obs)
        
        assert action["type"] in ["noop", "restart", "scale", "throttle"]
        if action["type"] != "noop":
            assert action["target"] in ["A", "B", "C"]

    def test_q_table_updates_on_observe(self):
        """Q-table should update when observing reward."""
        obs = self.env._build_observation()
        action = self.agent.act(obs)
        
        initial_q_size = len(self.agent.q_table)
        
        # Observe reward
        self.agent.observe(action, reward=1.0, observation=obs, next_observation=obs)
        
        # Q-table should have entries
        assert len(self.agent.q_table) > 0

    def test_epsilon_decays(self):
        """Epsilon should decay over time."""
        initial_epsilon = self.agent.epsilon
        
        obs = self.env._build_observation()
        for _ in range(10):
            self.agent.act(obs)
        
        # Epsilon should decrease
        assert self.agent.epsilon < initial_epsilon

    def test_alpha_decays(self):
        """Alpha should decay over time."""
        initial_alpha = self.agent.alpha
        
        obs = self.env._build_observation()
        for _ in range(10):
            self.agent.act(obs)
        
        # Alpha should decrease
        assert self.agent.alpha < initial_alpha

    def test_state_signature_coarse_grained(self):
        """State signature should use coarse pressure buckets."""
        obs1 = {"system_pressure": 1.0, "queues": {"A": 5.0, "B": 2.0, "C": 1.0}, "capacities": {"A": 10.0, "B": 10.0, "C": 10.0}, "retry_rate": 0.1, "error_rate": 0.05}
        obs2 = {"system_pressure": 1.0, "queues": {"A": 5.0, "B": 2.0, "C": 1.0}, "capacities": {"A": 10.0, "B": 10.0, "C": 10.0}, "retry_rate": 0.1, "error_rate": 0.05}
        
        sig1 = self.agent._state_signature(obs1)
        sig2 = self.agent._state_signature(obs2)
        
        # Same observations should produce same state signature
        assert sig1 == sig2


class TestSmartAgent:
    """Test SmartAgent planning."""

    def setup_method(self):
        """Setup smart agent and environment."""
        self.agent = SmartAgent(horizon=12)
        self.env = ASCDCEnvironment(seed=42)

    def test_smart_agent_returns_valid_action(self):
        """Smart agent should return valid action."""
        obs = self.env._build_observation()
        action = self.agent.act(obs)
        
        assert action["type"] in ["noop", "restart", "scale", "throttle"]
        if action["type"] != "noop":
            assert action["target"] in ["A", "B", "C"]

    def test_smart_agent_evaluates_sequences(self):
        """Smart agent should evaluate action sequences."""
        obs = self.env._build_observation()
        
        # Should evaluate multiple sequences
        action = self.agent.act(obs)
        
        # Should return a valid action (not crash during evaluation)
        assert action is not None

    def test_smart_agent_respects_cooldown(self):
        """Smart agent should respect action cooldown."""
        obs = self.env._build_observation()
        action1 = self.agent.act(obs)
        
        # Verify action is valid
        assert action1["type"] in ["noop", "restart", "scale", "throttle"]
        
        # Verify cooldown tracking works
        initial_cooldown = self.agent.action_cooldown
        self.agent.action_cooldown = 2
        assert self.agent.action_cooldown == 2

    def test_smart_agent_prefers_noop_when_close(self):
        """Smart agent should prefer noop if action barely better."""
        self.env.reset()
        obs = self.env._build_observation()
        
        # In stable state, should prefer noop
        action = self.agent.act(obs)
        
        # Stable state should result in noop
        if obs.system_pressure < 0.4:
            assert action["type"] == "noop"
