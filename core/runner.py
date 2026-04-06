from __future__ import annotations

from typing import Any, Dict, List

from core.counterfactual import CounterfactualEvaluator


class TaskRunner:
    def __init__(self, env: Any):
        """
        env: instance of ASCDCEnvironment
        """
        self.env = env
        self.counterfactual_evaluator = CounterfactualEvaluator()

    def run_task(self, task_config: dict, agent: Any) -> List[Dict[str, Any]]:
        """
        Runs one full episode using the provided task_config
        and agent.

        Returns:
            trajectory: List[dict]
        """

        # Reset environment with injected task config
        observation = self.env.reset(config=task_config)

        done = False
        trajectory: List[Dict[str, Any]] = []

        while not done:
            # Agent selects action
            action = agent.act(observation)
            counterfactual = self.counterfactual_evaluator.evaluate(self.env, action)

            # Environment step
            next_observation, reward, done, info = self.env.step(action)
            info.update(counterfactual)

            # Store full transition (grader-critical)
            trajectory.append(
                {
                    "timestep": self.env.timestep,
                    "observation": observation,
                    "action": action,
                    "reward": reward,
                    "next_observation": next_observation,
                    "done": done,
                    "info": info,
                }
            )

            # Move forward
            observation = next_observation

        return trajectory


__all__ = ["TaskRunner"]
