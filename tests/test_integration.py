"""Integration tests for ASCDC end-to-end pipeline."""

import pytest
from copy import deepcopy

from env.environment import ASCDCEnvironment
from core.agents.smart_agent import SmartAgent
from core.counterfactual import CounterfactualEvaluator
from grader.grader import ASCDCGrader


class TestEndToEndPipeline:
    """Test full pipeline: environment → agent → counterfactual → grader."""

    def setup_method(self):
        """Setup test environment and components."""
        self.env = ASCDCEnvironment(seed=42)
        self.agent = SmartAgent(horizon=12)
        self.evaluator = CounterfactualEvaluator()
        self.grader = ASCDCGrader()

    def test_full_episode_execution(self):
        """Run full episode and verify all components work together."""
        obs = self.env.reset()
        trajectory = []

        for step_idx in range(20):
            # Agent decides
            action = self.agent.act(self.env)
            assert action is not None
            assert "type" in action
            assert "target" in action

            # Counterfactual evaluation
            cf_result = self.evaluator.evaluate(self.env, action)
            assert "counterfactual_impact" in cf_result
            assert "was_action_necessary" in cf_result

            # Step environment
            next_obs, reward, done, info = self.env.step(action)
            info.update(cf_result)

            trajectory.append({
                "timestep": self.env.timestep,
                "observation": obs,
                "action": action,
                "reward": reward,
                "next_observation": next_obs,
                "done": done,
                "info": info,
            })

            obs = next_obs
            if done:
                break

        # Grade trajectory
        score = self.grader.grade(trajectory)
        assert 0.0 <= score <= 1.0
        assert len(trajectory) > 0

    def test_deterministic_execution(self):
        """Same seed produces identical trajectory."""
        env1 = ASCDCEnvironment(seed=42)
        env2 = ASCDCEnvironment(seed=42)
        agent1 = SmartAgent(horizon=12)
        agent2 = SmartAgent(horizon=12)

        obs1 = env1.reset()
        obs2 = env2.reset()

        for _ in range(10):
            action1 = agent1.act(env1)
            action2 = agent2.act(env2)

            assert action1["type"] == action2["type"]
            assert action1["target"] == action2["target"]

            obs1, _, done1, _ = env1.step(action1)
            obs2, _, done2, _ = env2.step(action2)

            state1 = env1.state()
            state2 = env2.state()
            assert state1["system_pressure"] == state2["system_pressure"]
            assert done1 == done2

            if done1:
                break

    def test_counterfactual_fairness(self):
        """Counterfactual evaluation prevents trivial policies."""
        obs = self.env.reset()

        # Evaluate noop
        noop_cf = self.evaluator.evaluate(self.env, {"type": "noop", "target": None})
        assert noop_cf["counterfactual_impact"] == 0.0
        assert noop_cf["was_action_necessary"] is False

        # Evaluate action
        action_cf = self.evaluator.evaluate(self.env, {"type": "scale", "target": "A"})
        # Action should have non-zero impact (positive or negative)
        assert isinstance(action_cf["counterfactual_impact"], float)

    def test_grading_consistency(self):
        """Grading produces consistent scores for same trajectory."""
        obs = self.env.reset()
        trajectory = []

        for _ in range(15):
            action = self.agent.act(self.env)
            cf_result = self.evaluator.evaluate(self.env, action)
            next_obs, reward, done, info = self.env.step(action)
            info.update(cf_result)

            trajectory.append({
                "timestep": self.env.timestep,
                "observation": obs,
                "action": action,
                "reward": reward,
                "next_observation": next_obs,
                "done": done,
                "info": info,
            })

            obs = next_obs
            if done:
                break

        # Grade multiple times
        score1 = self.grader.grade(trajectory)
        score2 = self.grader.grade(deepcopy(trajectory))
        assert score1 == score2

    def test_agent_handles_high_pressure(self):
        """Agent responds appropriately to high-pressure scenarios."""
        config = {
            "seed": 42,
            "base_load": {"A": 30.0, "B": 5.0, "C": 2.0},
            "capacities": {"A": 20.0, "B": 10.0, "C": 10.0},
            "initial_queues": {"A": 5.0, "B": 8.0, "C": 2.0},
            "initial_budget": 100.0,
            "max_timesteps": 50,
        }
        env = ASCDCEnvironment(seed=42)
        obs = env.reset(config=config)
        agent = SmartAgent(horizon=12)

        high_pressure_steps = 0
        for _ in range(20):
            action = agent.act(env)
            obs, _, done, _ = env.step(action)

            state = env.state()
            if state.get("system_pressure", 0) > 2.0:
                high_pressure_steps += 1
                # In high pressure, agent should not always choose noop
                assert action["type"] != "noop" or high_pressure_steps > 3

            if done:
                break

    def test_trajectory_grading_range(self):
        """Grading scores are always in valid range."""
        for seed in [42, 123, 456]:
            env = ASCDCEnvironment(seed=seed)
            obs = env.reset()
            agent = SmartAgent(horizon=12)
            trajectory = []

            for _ in range(25):
                action = agent.act(env)
                cf_result = self.evaluator.evaluate(env, action)
                next_obs, reward, done, info = env.step(action)
                info.update(cf_result)

                trajectory.append({
                    "timestep": env.timestep,
                    "observation": obs,
                    "action": action,
                    "reward": reward,
                    "next_observation": next_obs,
                    "done": done,
                    "info": info,
                })

                obs = next_obs
                if done:
                    break

            score = self.grader.grade(trajectory)
            assert 0.0 <= score <= 1.0, f"Score {score} out of range for seed {seed}"
