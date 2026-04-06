from __future__ import annotations

from copy import deepcopy
import math
from typing import Any, Dict, Iterable, Mapping


class CounterfactualEvaluator:
    def __init__(self, horizon: int = 5) -> None:
        self.horizon = max(3, min(5, int(horizon)))

    def evaluate(self, env: Any, action: Any) -> Dict[str, Any]:
        action_outcome = self._simulate(env, action)
        noop_outcome = self._simulate(env, {"type": "noop", "target": None})
        impact = self._safe_float(action_outcome - noop_outcome)

        return {
            "counterfactual_impact": round(impact, 6),
            "was_action_necessary": self._is_action_necessary(action, impact),
        }

    def _simulate(self, env: Any, initial_action: Any) -> float:
        simulated_env = deepcopy(env)
        total_reward = 0.0
        action = deepcopy(initial_action)

        for step_index in range(self.horizon):
            _, reward, done, _ = simulated_env.step(action)
            total_reward += self._safe_float(reward)
            if done:
                break
            if step_index == 0:
                action = {"type": "noop", "target": None}

        return self._safe_float(total_reward)

    def _is_action_necessary(self, action: Any, impact: float) -> bool:
        return self._get_action_type(action) != "noop" and impact > 0.0

    @staticmethod
    def _get_action_type(action: Any) -> str:
        if isinstance(action, Mapping):
            return str(action.get("type") or action.get("action_type") or "noop").lower()
        return str(
            getattr(action, "type", getattr(action, "action_type", "noop"))
        ).lower()

    @staticmethod
    def _safe_float(value: Any) -> float:
        numeric = float(value)
        if not math.isfinite(numeric):
            return 0.0
        return numeric


def compute_counterfactual_metrics(trajectory: Iterable[Mapping[str, Any]]) -> Dict[str, float]:
    steps = list(trajectory)
    action_steps = [
        step
        for step in steps
        if CounterfactualEvaluator._get_action_type(step.get("action")) != "noop"
    ]
    if not action_steps:
        return {
            "necessary_action_ratio": 0.0,
            "average_impact": 0.0,
            "positive_impact_rate": 0.0,
        }

    impacts = [
        CounterfactualEvaluator._safe_float(
            step.get("info", {}).get("counterfactual_impact", 0.0)
        )
        for step in action_steps
    ]
    necessary_actions = sum(
        1
        for step in action_steps
        if bool(step.get("info", {}).get("was_action_necessary", False))
    )
    positive_impacts = sum(1 for impact in impacts if impact > 0.0)
    total_actions = len(action_steps)

    return {
        "necessary_action_ratio": round(necessary_actions / total_actions, 4),
        "average_impact": round(sum(impacts) / total_actions, 6),
        "positive_impact_rate": round(positive_impacts / total_actions, 4),
    }


__all__ = ["CounterfactualEvaluator", "compute_counterfactual_metrics"]
