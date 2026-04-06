from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Mapping, Optional

from core.counterfactual import CounterfactualEvaluator


class OperatorAgent:
    QUEUE_ORDER = ("A", "B", "C")
    ACTION_TYPES = ("restart", "scale", "throttle")

    def __init__(
        self,
        env: Any,
        evaluator: Optional[CounterfactualEvaluator] = None,
    ) -> None:
        self.env = env
        self.evaluator = evaluator or CounterfactualEvaluator()
        self.history: List[Dict[str, Any]] = []

    def act(self, observation: Any) -> Dict[str, Any]:
        candidates = [self._evaluate_candidate(action) for action in self._candidate_actions()]
        candidates.sort(
            key=lambda item: (
                item["adjusted_impact"],
                item["impact"],
                1 if item["action"]["type"] == "noop" else 0,
            ),
            reverse=True,
        )

        fallback_action = next(
            item for item in candidates if item["action"]["type"] == "noop"
        )
        best_action = candidates[0]
        selected = best_action if best_action["adjusted_impact"] > 0.0 else fallback_action
        confidence = self._compute_confidence(candidates, selected)

        response = {
            "action": self._response_action(selected["action"]),
            "reasoning": {
                "best_action": selected["label"],
                "confidence": round(confidence, 2),
                "impact": round(selected["impact"], 6),
                "was_necessary": bool(selected["impact"] > 0.0 and selected["action"]["type"] != "noop"),
                "alternative_actions": [
                    {
                        "action": self._response_action(candidate["action"]),
                        "label": candidate["label"],
                        "impact": round(candidate["impact"], 6),
                        "necessary": bool(
                            candidate["impact"] > 0.0 and candidate["action"]["type"] != "noop"
                        ),
                    }
                    for candidate in candidates
                ],
                "explanation": self.explain_decision(
                    observation,
                    selected["action"],
                    selected["impact"],
                ),
            },
        }

        self.history.append(
            {
                "observation": self._snapshot_observation(observation),
                "action": deepcopy(selected["action"]),
                "impact": round(selected["impact"], 6),
            }
        )
        self.history = self.history[-100:]

        return response

    def explain_decision(self, state: Any, action: Mapping[str, Any], impact: float) -> str:
        pressure = self._extract_pressure(state)
        action_type = str(action.get("type", "noop")).lower()
        target = action.get("target")

        if action_type == "noop":
            if pressure >= 1.0:
                return "Available interventions do not outperform waiting over the current counterfactual horizon."
            return "System pressure remains manageable, so waiting is preferred over unnecessary intervention."

        if action_type == "scale":
            return f"Scaling {target} improves projected reward more than waiting under the current delayed load pattern."

        if action_type == "restart":
            return f"Restarting {target} is expected to clear accumulating pressure despite its delayed recovery cost."

        if action_type == "throttle":
            return f"Throttling {target} reduces projected downstream pressure better than allowing load to continue unchecked."

        return f"Selected {action_type} with projected impact {impact:.3f}."

    def _candidate_actions(self) -> List[Dict[str, Any]]:
        candidates: List[Dict[str, Any]] = [{"type": "noop", "target": None}]
        for action_type in self.ACTION_TYPES:
            for queue in self.QUEUE_ORDER:
                candidates.append({"type": action_type, "target": queue})
        return candidates

    def _evaluate_candidate(self, action: Dict[str, Any]) -> Dict[str, Any]:
        evaluation = self.evaluator.evaluate(self.env, action)
        impact = float(evaluation["counterfactual_impact"])
        penalty = self._memory_penalty(action)
        adjusted_impact = impact - penalty

        return {
            "action": deepcopy(action),
            "label": self._action_label(action),
            "impact": impact,
            "adjusted_impact": adjusted_impact,
        }

    def _memory_penalty(self, action: Mapping[str, Any]) -> float:
        label = self._action_label(action)
        repeated_bad_actions = sum(
            1
            for item in self.history
            if self._action_label(item["action"]) == label and float(item["impact"]) <= 0.0
        )
        return repeated_bad_actions * 0.15

    def _compute_confidence(
        self,
        candidates: List[Dict[str, Any]],
        selected: Dict[str, Any],
    ) -> float:
        remaining = [candidate for candidate in candidates if candidate is not selected]
        if not remaining:
            return 1.0

        next_best = max(candidate["adjusted_impact"] for candidate in remaining)
        margin = max(0.0, selected["adjusted_impact"] - next_best)
        baseline = 0.55 if selected["action"]["type"] != "noop" else 0.5
        return max(0.0, min(1.0, baseline + margin))

    def _response_action(self, action: Mapping[str, Any]) -> Dict[str, Any]:
        action_type = str(action.get("type", "noop")).lower()
        return {
            "type": action_type,
            "action_type": action_type,
            "target": action.get("target"),
            "amount": 1.0,
        }

    def _snapshot_observation(self, observation: Any) -> Dict[str, Any]:
        if isinstance(observation, Mapping):
            return deepcopy(dict(observation))
        if hasattr(observation, "model_dump") and callable(observation.model_dump):
            return deepcopy(observation.model_dump())
        if hasattr(observation, "dict") and callable(observation.dict):
            return deepcopy(observation.dict())
        if hasattr(observation, "__dict__"):
            return deepcopy(
                {
                    key: value
                    for key, value in vars(observation).items()
                    if not key.startswith("_")
                }
            )
        return {}

    def _extract_pressure(self, state: Any) -> float:
        if isinstance(state, Mapping):
            return float(state.get("system_pressure", 0.0))
        return float(getattr(state, "system_pressure", 0.0))

    @staticmethod
    def _action_label(action: Mapping[str, Any]) -> str:
        action_type = str(action.get("type", "noop")).upper()
        target = action.get("target")
        return f"{action_type} {target}" if target else action_type


__all__ = ["OperatorAgent"]
