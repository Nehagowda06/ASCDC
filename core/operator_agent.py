from __future__ import annotations

from copy import deepcopy
import math
import random
from typing import Any, Dict, List, Mapping, Optional

from core.counterfactual import CounterfactualEvaluator

try:
    from core.models.policy_agent import PolicyAgent
except Exception:
    PolicyAgent = None


class OperatorAgent:
    QUEUES = ("A", "B", "C")
    ACTION_TYPES = ("restart", "scale", "throttle")

    def __init__(self, env: Any, policy_agent: Optional["PolicyAgent"] = None) -> None:
        self.env = env
        self.evaluator = CounterfactualEvaluator()
        self.policy_agent = policy_agent
        if self.policy_agent is None and PolicyAgent is not None:
            try:
                self.policy_agent = PolicyAgent()
            except Exception:
                self.policy_agent = None
        self.history: List[Dict[str, Any]] = []

    def act(self, observation: Any) -> Dict[str, Any]:
        evaluated_actions = [
            self._evaluate_action(observation, action) for action in self._candidate_actions()
        ]
        evaluated_actions.sort(
            key=lambda item: (
                item["score"],
                item["impact"],
                1 if item["action"]["type"] != "noop" else 0,
            ),
            reverse=True,
        )

        best_candidate = evaluated_actions[0]
        second_candidate = (
            evaluated_actions[1] if len(evaluated_actions) > 1 else evaluated_actions[0]
        )
        non_noop_actions = [
            a for a in evaluated_actions if a["action"]["type"] != "noop"
        ]

        if best_candidate["action"]["type"] == "noop":
            if second_candidate["impact"] > -0.5:
                chosen = second_candidate
            else:
                chosen = best_candidate
        else:
            chosen = best_candidate

        if all(a["impact"] <= 0 for a in non_noop_actions):
            if non_noop_actions:
                chosen = max(non_noop_actions, key=lambda x: x["score"])

        if random.random() < 0.1:
            non_noop = [a for a in evaluated_actions if a["action"]["type"] != "noop"]
            if non_noop:
                chosen = random.choice(non_noop)

        print("EVALUATED ACTIONS:", evaluated_actions)
        print("CHOSEN ACTION:", chosen)

        chosen_impact = float(chosen["impact"])
        was_necessary = chosen["action"]["type"] != "noop" and chosen_impact > 0.0
        confidence = self._confidence(chosen, best_candidate, evaluated_actions)
        explanation = self._explain(chosen, best_candidate)
        ranked_actions = [
            {
                "action": self._response_action(candidate["action"]),
                "label": self._action_label(candidate["action"]),
                "impact": round(float(candidate["impact"]), 6),
                "model_score": round(float(candidate["model_score"]), 6),
                "necessary": bool(
                    candidate["action"]["type"] != "noop" and float(candidate["impact"]) > 0.0
                ),
            }
            for candidate in evaluated_actions
        ]

        self.history.append(
            {
                "observation": self._snapshot(observation),
                "action": deepcopy(chosen["action"]),
                "impact": round(chosen_impact, 6),
            }
        )
        self.history = self.history[-100:]

        return {
            "action": self._response_action(chosen["action"]),
            "impact": round(chosen_impact, 6),
            "was_necessary": was_necessary,
            "confidence": round(confidence, 4),
            "explanation": explanation,
            "evaluated_actions": ranked_actions,
            "reasoning": {
                "best_action": self._action_label(chosen["action"]),
                "impact": round(chosen_impact, 6),
                "was_necessary": was_necessary,
                "confidence": round(confidence, 4),
                "explanation": explanation,
                "alternative_actions": ranked_actions,
            },
        }

    def model_info(self) -> Dict[str, Any]:
        if self.policy_agent is None:
            return {
                "loaded": False,
                "source": "unavailable",
            }
        return self.policy_agent.model_info()

    def _candidate_actions(self) -> List[Dict[str, Any]]:
        candidates: List[Dict[str, Any]] = [{"type": "noop", "target": None}]
        for action_type in self.ACTION_TYPES:
            for queue in self.QUEUES:
                candidates.append({"type": action_type, "target": queue})
        return candidates

    def _evaluate_action(self, observation: Any, action: Dict[str, Any]) -> Dict[str, Any]:
        impact = self._safe_float(self.evaluator.evaluate(self.env, action)["counterfactual_impact"])
        model_score = self._model_score(observation, action)
        penalty = self._negative_history_penalty(action)
        normalized_impact = impact * 0.5
        action_bonus = 0.4 if action["type"] != "noop" else 0.0
        model_weight = 0.3
        impact_weight = 0.5
        score = (
            impact_weight * normalized_impact
            + model_weight * model_score
            - penalty
            + action_bonus
        )
        if action["type"] == "noop":
            score -= 0.2

        return {
            "action": deepcopy(action),
            "impact": impact,
            "model_score": model_score,
            "score": score,
        }

    def _negative_history_penalty(self, action: Mapping[str, Any]) -> float:
        action_key = self._action_key(action)
        repeat_count = sum(
            1
            for item in self.history
            if self._action_key(item["action"]) == action_key and float(item["impact"]) < 0.0
        )
        return repeat_count * 0.25

    def _model_score(self, observation: Any, action: Mapping[str, Any]) -> float:
        if self.policy_agent is None:
            return 0.0
        try:
            return self._safe_float(self.policy_agent.score_action(observation, action))
        except Exception:
            return 0.0

    def _confidence(
        self,
        chosen: Mapping[str, Any],
        best_candidate: Mapping[str, Any],
        evaluated_actions: List[Dict[str, Any]],
    ) -> float:
        max_impact = max(max(abs(float(item["impact"])) for item in evaluated_actions), 1.0)
        if chosen["action"]["type"] == "noop":
            return max(0.0, min(1.0, abs(float(best_candidate["score"])) / max_impact))
        return max(0.0, min(1.0, float(chosen["score"]) / max_impact))

    def _explain(
        self,
        chosen: Mapping[str, Any],
        best_candidate: Mapping[str, Any],
    ) -> str:
        action_type = str(chosen["action"].get("type", "noop")).lower()
        target = chosen["action"].get("target")
        impact = float(chosen["impact"])

        if action_type == "noop":
            if float(best_candidate["impact"]) <= 0.0:
                return "System stabilizes without intervention. Acting would reduce projected performance."
            return "Recent negative outcomes make intervention riskier than waiting at this step."

        if action_type == "scale":
            return f"Scaling {target} produces the strongest projected improvement over the noop baseline."
        if action_type == "restart":
            return f"Restarting {target} clears enough projected pressure to outperform waiting."
        if action_type == "throttle":
            return f"Throttling {target} reduces projected pressure more effectively than waiting."
        return f"{self._action_label(chosen['action'])} is projected to improve reward by {impact:.2f}."

    @staticmethod
    def _action_key(action: Mapping[str, Any]) -> str:
        action_type = str(action.get("type", "noop")).lower()
        target = action.get("target")
        return f"{action_type}:{target}"

    @staticmethod
    def _response_action(action: Mapping[str, Any]) -> Dict[str, Any]:
        action_type = str(action.get("type", "noop")).lower()
        response = {
            "type": action_type,
            "action_type": action_type,
        }
        target = action.get("target")
        if target is not None:
            response["target"] = target
        return response

    @staticmethod
    def _snapshot(observation: Any) -> Dict[str, Any]:
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

    @staticmethod
    def _action_label(action: Mapping[str, Any]) -> str:
        action_type = str(action.get("type", "noop")).upper()
        target = action.get("target")
        return f"{action_type} {target}" if target else action_type

    @staticmethod
    def _safe_float(value: Any) -> float:
        numeric = float(value)
        if not math.isfinite(numeric):
            return 0.0
        return numeric


__all__ = ["OperatorAgent"]
