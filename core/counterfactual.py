from __future__ import annotations

from copy import deepcopy
import math
from typing import Any, Dict, Iterable, Mapping

from env.environment import COUNTERFACTUAL_HORIZON


class CounterfactualEvaluator:
    def __init__(self) -> None:
        self.horizon = COUNTERFACTUAL_HORIZON
        self.min_significant_impact = 0.75
        self.min_positive_impact = 0.4
        self.relative_impact_floor = 0.12

    def evaluate(self, env: Any, action: Any) -> Dict[str, Any]:
        # Guard against nested counterfactuals
        if getattr(env, "_cf_active", False):
            return {
                "counterfactual_impact": 0.0,
                "counterfactual_ratio": 0.0,
                "action_rollout_reward": 0.0,
                "noop_rollout_reward": 0.0,
                "had_meaningful_impact": False,
                "was_action_necessary": False,
            }

        action_outcome = self._simulate(env, action)
        noop_outcome = self._simulate(env, {"type": "noop", "target": None})
        impact = self._safe_float(action_outcome - noop_outcome)
        impact_ratio = impact / max(abs(noop_outcome), 1.0)
        meaningful_impact = self._has_meaningful_impact(action, impact, impact_ratio)

        return {
            "counterfactual_impact": round(impact, 6),
            "counterfactual_ratio": round(impact_ratio, 6),
            "action_rollout_reward": round(action_outcome, 6),
            "noop_rollout_reward": round(noop_outcome, 6),
            "had_meaningful_impact": meaningful_impact,
            "was_action_necessary": self._is_action_necessary(action, impact, impact_ratio),
        }

    def _simulate(self, env: Any, initial_action: Any) -> float:
        simulated_env = deepcopy(env)
        if hasattr(env, "rng") and hasattr(simulated_env, "rng"):
            simulated_env.rng.setstate(env.rng.getstate())
        total_reward = 0.0
        action = deepcopy(initial_action)

        for step_index in range(self.horizon):
            _, reward, done, _ = simulated_env.step(
                action,
                evaluate_counterfactual=False,
            )
            total_reward += self._safe_float(reward)
            if done:
                break
            if step_index == 0:
                action = {"type": "noop", "target": None}

        return self._safe_float(total_reward)

    def _has_meaningful_impact(self, action: Any, impact: float, impact_ratio: float) -> bool:
        return (
            self._get_action_type(action) != "noop"
            and impact >= self.min_positive_impact
            and impact_ratio >= 0.06
        )

    def _is_action_necessary(self, action: Any, impact: float, impact_ratio: float) -> bool:
        return (
            self._get_action_type(action) != "noop"
            and impact >= self.min_significant_impact
            and impact_ratio >= self.relative_impact_floor
        )

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
    positive_impacts = sum(
        1 for step in action_steps
        if bool(step.get("info", {}).get("had_meaningful_impact", False))
    )
    total_actions = len(action_steps)

    return {
        "necessary_action_ratio": round(necessary_actions / total_actions, 4),
        "average_impact": round(sum(impacts) / total_actions, 6),
        "positive_impact_rate": round(positive_impacts / total_actions, 4),
    }


__all__ = ["CounterfactualEvaluator", "compute_counterfactual_metrics"]
