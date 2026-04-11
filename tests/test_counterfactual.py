"""Unit tests for counterfactual evaluation algorithm."""

import pytest
from core.counterfactual import CounterfactualEvaluator, compute_counterfactual_metrics
from env.environment import ASCDCEnvironment


class TestCounterfactualEvaluator:
    """Test counterfactual evaluation correctness."""

    def setup_method(self):
        """Setup test environment."""
        self.evaluator = CounterfactualEvaluator()
        self.env = ASCDCEnvironment(seed=42)

    def test_evaluate_returns_dict_with_required_keys(self):
        """Counterfactual evaluation returns all required keys."""
        action = {"type": "scale", "target": "A"}
        result = self.evaluator.evaluate(self.env, action)
        
        required_keys = {
            "counterfactual_impact",
            "counterfactual_ratio",
            "action_rollout_reward",
            "noop_rollout_reward",
            "had_meaningful_impact",
            "was_action_necessary",
        }
        assert required_keys.issubset(result.keys())

    def test_noop_action_has_zero_impact(self):
        """Noop action should have zero counterfactual impact."""
        action = {"type": "noop", "target": None}
        result = self.evaluator.evaluate(self.env, action)
        
        assert result["counterfactual_impact"] == 0.0
        assert result["was_action_necessary"] is False

    def test_impact_is_action_minus_noop(self):
        """Impact should be action_reward - noop_reward."""
        action = {"type": "scale", "target": "A"}
        result = self.evaluator.evaluate(self.env, action)
        
        expected_impact = result["action_rollout_reward"] - result["noop_rollout_reward"]
        assert abs(result["counterfactual_impact"] - expected_impact) < 0.01

    def test_necessary_action_threshold(self):
        """Action is necessary only if impact >= 0.75 AND ratio >= 0.12."""
        # Create high-pressure environment
        self.env.reset(config={
            "seed": 42,
            "base_load": {"A": 30.0, "B": 5.0, "C": 2.0},
            "capacities": {"A": 20.0, "B": 10.0, "C": 10.0},
            "initial_queues": {"A": 5.0, "B": 8.0, "C": 2.0},
            "initial_budget": 100.0,
            "max_timesteps": 50,
        })
        
        action = {"type": "restart", "target": "A"}
        result = self.evaluator.evaluate(self.env, action)
        
        # Verify threshold logic
        if result["was_action_necessary"]:
            assert result["counterfactual_impact"] >= 0.75
            assert result["counterfactual_ratio"] >= 0.12

    def test_nested_counterfactual_guard(self):
        """Nested counterfactuals should return zero impact."""
        self.env._cf_active = True
        action = {"type": "scale", "target": "A"}
        result = self.evaluator.evaluate(self.env, action)
        
        assert result["counterfactual_impact"] == 0.0
        assert result["was_action_necessary"] is False

    def test_deterministic_evaluation(self):
        """Same seed should produce same evaluation."""
        env1 = ASCDCEnvironment(seed=42)
        env2 = ASCDCEnvironment(seed=42)
        
        action = {"type": "scale", "target": "A"}
        result1 = self.evaluator.evaluate(env1, action)
        result2 = self.evaluator.evaluate(env2, action)
        
        assert result1["counterfactual_impact"] == result2["counterfactual_impact"]
        assert result1["was_action_necessary"] == result2["was_action_necessary"]


class TestComputeCounterfactualMetrics:
    """Test counterfactual metrics computation."""

    def test_empty_trajectory_returns_zeros(self):
        """Empty trajectory should return zero metrics."""
        trajectory = []
        metrics = compute_counterfactual_metrics(trajectory)
        
        assert metrics["necessary_action_ratio"] == 0.0
        assert metrics["average_impact"] == 0.0
        assert metrics["positive_impact_rate"] == 0.0

    def test_noop_only_trajectory_returns_zeros(self):
        """Trajectory with only noops should return zero metrics."""
        trajectory = [
            {"action": {"type": "noop", "target": None}, "info": {}},
            {"action": {"type": "noop", "target": None}, "info": {}},
        ]
        metrics = compute_counterfactual_metrics(trajectory)
        
        assert metrics["necessary_action_ratio"] == 0.0
        assert metrics["average_impact"] == 0.0
        assert metrics["positive_impact_rate"] == 0.0

    def test_metrics_ratios_in_valid_range(self):
        """All metrics should be in [0, 1] range."""
        trajectory = [
            {
                "action": {"type": "scale", "target": "A"},
                "info": {
                    "counterfactual_impact": 0.5,
                    "was_action_necessary": True,
                    "had_meaningful_impact": True,
                },
            },
            {
                "action": {"type": "throttle", "target": "B"},
                "info": {
                    "counterfactual_impact": 0.2,
                    "was_action_necessary": False,
                    "had_meaningful_impact": False,
                },
            },
        ]
        metrics = compute_counterfactual_metrics(trajectory)
        
        assert 0.0 <= metrics["necessary_action_ratio"] <= 1.0
        assert 0.0 <= metrics["positive_impact_rate"] <= 1.0
