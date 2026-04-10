"""
Simple, working recommendation system
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Mapping, Optional
import logging

from env.environment import ASCDCEnvironment
from agents import get_current_agent, get_current_agent_name
from core.counterfactual import CounterfactualEvaluator

logger = logging.getLogger(__name__)

class SimpleRecommendationSystem:
    """Simple, reliable recommendation system."""
    
    def __init__(self, env: ASCDCEnvironment):
        self.env = env
        self.counterfactual_evaluator = CounterfactualEvaluator()
        self.step_count = 0
        
    def recommend(self, current_state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Generate a recommendation."""
        try:
            self.step_count += 1
            
            # Get current observation
            if current_state:
                observation = self._normalize_observation(current_state)
            else:
                observation = self._normalize_observation(self.env.state())

            evaluation_env = self._build_evaluation_env(observation)
            
            # Get agent recommendation
            agent = get_current_agent()
            agent_action = self._normalize_action(agent.act(evaluation_env))
            
            # Evaluate all possible actions for comparison
            all_actions = self._generate_all_actions()
            evaluated_actions = []
            
            for action in all_actions:
                try:
                    evaluation = self.counterfactual_evaluator.evaluate(evaluation_env, action)
                    evaluated_actions.append({
                        "action": self._normalize_action(action),
                        "impact": evaluation.get("counterfactual_impact", 0),
                        "necessary": evaluation.get("was_action_necessary", False),
                        "score": evaluation.get("counterfactual_impact", 0)
                    })
                except Exception as e:
                    logger.warning(f"Failed to evaluate action {action}: {e}")
                    evaluated_actions.append({
                        "action": action,
                        "impact": 0,
                        "necessary": False,
                        "score": 0
                    })

            ranked_actions = sorted(
                evaluated_actions,
                key=lambda item: (
                    item["impact"],
                    item["necessary"],
                    item["action"]["type"] != "noop",
                ),
                reverse=True,
            )
            best_eval = ranked_actions[0] if ranked_actions else {
                "action": {"type": "noop", "target": None},
                "impact": 0.0,
                "necessary": False,
                "score": 0.0,
            }

            agent_eval = self._find_action_evaluation(agent_action, ranked_actions)
            agent_rank = self._find_action_rank(agent_action, ranked_actions)
            
            # Confidence is based on the winning action's lead over the next-best option.
            confidence = self._calculate_confidence(best_eval, ranked_actions, observation)
            
            # Generate explanation
            explanation = self._generate_explanation(best_eval, observation, ranked_actions, agent_eval, agent_rank)
            alternatives = [
                {
                    "action": eval_item["action"],
                    "label": self._format_action_label(eval_item["action"]),
                    "impact": eval_item["impact"],
                    "necessary": eval_item["necessary"],
                }
                for eval_item in ranked_actions
            ]
            
            return {
                "action": best_eval["action"],
                "impact": best_eval["impact"],
                "was_necessary": best_eval["necessary"],
                "confidence": confidence,
                "explanation": explanation,
                "evaluated_actions": alternatives,
                "reasoning": {
                    "best_action": self._format_action_label(best_eval["action"]),
                    "confidence": confidence,
                    "impact": best_eval["impact"],
                    "was_necessary": best_eval["necessary"],
                    "alternative_actions": alternatives,
                    "explanation": explanation,
                    "agent_name": get_current_agent_name(),
                    "agent_action": self._format_action_label(agent_action),
                    "agent_action_impact": agent_eval["impact"] if agent_eval else None,
                    "agent_action_rank": agent_rank,
                    "agent_action_matches_best": (
                        agent_eval is not None
                        and agent_eval["action"]["type"] == best_eval["action"]["type"]
                        and agent_eval["action"]["target"] == best_eval["action"]["target"]
                    ),
                }
            }
            
        except Exception as e:
            logger.error(f"Recommendation failed: {e}")
            return self._fallback_recommendation()
    
    def _generate_all_actions(self) -> List[Dict[str, Any]]:
        """Generate all possible actions."""
        actions = [{"type": "noop", "target": None}]
        
        for target in ["A", "B", "C"]:
            actions.extend([
                {"type": "scale", "target": target},
                {"type": "restart", "target": target},
                {"type": "throttle", "target": target}
            ])
        
        return actions
    
    def _normalize_observation(self, observation: Any) -> Dict[str, Any]:
        if isinstance(observation, Mapping):
            snapshot = dict(observation)
        elif hasattr(observation, "__dict__"):
            snapshot = dict(vars(observation))
        else:
            snapshot = {}

        snapshot["queues"] = {
            queue: float(value or 0.0)
            for queue, value in (snapshot.get("queues") or {}).items()
        }
        snapshot["capacities"] = {
            queue: max(float(value or 0.0), 1.0)
            for queue, value in (snapshot.get("capacities") or {}).items()
        }
        snapshot["latencies"] = {
            queue: float(value or 0.0)
            for queue, value in (snapshot.get("latencies") or {}).items()
        }
        snapshot["retry_rate"] = float(snapshot.get("retry_rate", 0.0) or 0.0)
        snapshot["error_rate"] = float(snapshot.get("error_rate", 0.0) or 0.0)
        snapshot["system_pressure"] = float(snapshot.get("system_pressure", 0.0) or 0.0)
        snapshot["remaining_budget"] = float(snapshot.get("remaining_budget", 0.0) or 0.0)
        snapshot["timestep"] = int(snapshot.get("timestep", 0) or 0)

        if "latency" not in snapshot:
            latencies = list(snapshot["latencies"].values())
            snapshot["latency"] = sum(latencies) / len(latencies) if latencies else 0.0

        return snapshot

    def _build_evaluation_env(self, observation: Dict[str, Any]) -> ASCDCEnvironment:
        simulated_env = deepcopy(self.env)
        simulated_env.queues = deepcopy(observation.get("queues", {}))

        if observation.get("capacities"):
            simulated_env.capacities = deepcopy(observation["capacities"])
        if observation.get("latencies"):
            simulated_env.latencies = deepcopy(observation["latencies"])
        if observation.get("base_load"):
            simulated_env.base_load = deepcopy(observation["base_load"])

        simulated_env.retry_rate = float(observation.get("retry_rate", simulated_env.retry_rate) or 0.0)
        simulated_env.error_rate = float(observation.get("error_rate", simulated_env.error_rate) or 0.0)
        simulated_env.system_pressure = float(observation.get("system_pressure", simulated_env.system_pressure) or 0.0)
        simulated_env.remaining_budget = float(observation.get("remaining_budget", simulated_env.remaining_budget) or 0.0)
        simulated_env.timestep = int(observation.get("timestep", simulated_env.timestep) or 0)
        return simulated_env

    def _normalize_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        action_type = str(action.get("type", action.get("action_type", "noop"))).lower()
        if action_type == "noop":
            return {"type": "noop", "target": None}
        return {
            "type": action_type,
            "target": action.get("target"),
        }

    def _find_action_evaluation(self, action: Dict[str, Any], evaluations: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        for evaluation in evaluations:
            if (
                evaluation["action"]["type"] == action["type"]
                and evaluation["action"]["target"] == action["target"]
            ):
                return evaluation
        return None

    def _find_action_rank(self, action: Dict[str, Any], evaluations: List[Dict[str, Any]]) -> Optional[int]:
        for index, evaluation in enumerate(evaluations, start=1):
            if (
                evaluation["action"]["type"] == action["type"]
                and evaluation["action"]["target"] == action["target"]
            ):
                return index
        return None

    def _queue_ratios(self, observation: Dict[str, Any]) -> Dict[str, float]:
        queues = observation.get("queues", {})
        capacities = observation.get("capacities", {})
        return {
            queue: float(queues.get(queue, 0.0)) / max(float(capacities.get(queue, 1.0)), 1.0)
            for queue in queues
        }

    def _looks_stable(self, observation: Dict[str, Any]) -> bool:
        max_ratio = max(self._queue_ratios(observation).values(), default=0.0)
        return (
            max_ratio < 0.35
            and float(observation.get("system_pressure", 0.0)) < 0.8
            and float(observation.get("retry_rate", 0.0)) < 0.25
            and float(observation.get("error_rate", 0.0)) < 0.2
        )

    def _calculate_confidence(
        self,
        chosen_eval: Dict[str, Any],
        ranked_evals: List[Dict[str, Any]],
        observation: Dict[str, Any],
    ) -> float:
        """Calculate confidence from the selected action's lead over the runner-up."""
        if not ranked_evals:
            return 0.1

        runner_up = ranked_evals[1] if len(ranked_evals) > 1 else None
        chosen_impact = float(chosen_eval.get("impact", 0.0) or 0.0)
        margin = chosen_impact - float(runner_up.get("impact", 0.0) if runner_up else 0.0)
        scale = abs(chosen_impact) + abs(float(runner_up.get("impact", 0.0) if runner_up else 0.0)) + 1.0
        normalized_margin = max(0.0, margin) / scale

        confidence = 0.4 + min(0.3, normalized_margin * 0.9)

        if chosen_impact > 0:
            confidence += 0.12
        if bool(chosen_eval.get("necessary", False)):
            confidence += 0.05

        action_type = chosen_eval["action"].get("type", "noop")
        if action_type == "noop":
            confidence += 0.1 if self._looks_stable(observation) else -0.12
        elif max(self._queue_ratios(observation).values(), default=0.0) >= 1.0:
            confidence += 0.05

        return round(max(0.1, min(0.95, confidence)), 3)

    def _generate_explanation(
        self,
        chosen_eval: Dict[str, Any],
        observation: Dict[str, Any],
        ranked_evals: List[Dict[str, Any]],
        agent_eval: Optional[Dict[str, Any]],
        agent_rank: Optional[int],
    ) -> str:
        """Generate explanation for the selected action."""
        action = chosen_eval["action"]
        action_type = action.get("type", "noop")
        target = action.get("target")
        impact = float(chosen_eval.get("impact", 0.0) or 0.0)
        max_queue = max(observation.get("queues", {}), key=lambda queue: observation["queues"].get(queue, 0.0), default="A")
        max_ratio = max(self._queue_ratios(observation).values(), default=0.0)
        runner_up = ranked_evals[1] if len(ranked_evals) > 1 else None
        margin = impact - float(runner_up.get("impact", 0.0) if runner_up else 0.0)

        if action_type == "noop":
            if self._looks_stable(observation):
                explanation = "System is stable enough that waiting outperforms every tested intervention over the next 5 steps."
            else:
                explanation = (
                    f"Waiting is still the least harmful option over the next 5 steps, even though queue {max_queue} "
                    f"is at {max_ratio:.2f}x capacity. Every tested intervention scored worse than NOOP from this state."
                )
        else:
            explanation = (
                f"{action_type.upper()} {target} has the strongest 5-step counterfactual impact "
                f"({impact:+.2f}) and beats the next-best action by {margin:+.2f}. "
                f"Queue {max_queue} is the dominant bottleneck at {max_ratio:.2f}x capacity."
            )
            if chosen_eval.get("necessary", False):
                explanation += " This is a necessary intervention relative to waiting."
            else:
                explanation += " This action is still preferred, but the advantage over waiting is limited."

        if agent_eval is not None and (
            agent_eval["action"]["type"] != chosen_eval["action"]["type"]
            or agent_eval["action"]["target"] != chosen_eval["action"]["target"]
        ):
            explanation += (
                f" The active agent proposed {self._format_action_label(agent_eval['action'])}"
                f" (rank {agent_rank}/{len(ranked_evals)}, impact {float(agent_eval['impact']):+.2f}),"
                f" so the counterfactual selector overrode it."
            )

        return explanation
    
    def _format_action_label(self, action: Dict[str, Any]) -> str:
        """Format action for display."""
        action_type = action.get("type", "noop")
        target = action.get("target", "")
        
        if action_type == "noop":
            return "NOOP"
        elif target:
            return f"{action_type.upper()} {target}"
        else:
            return action_type.upper()
    
    def _fallback_recommendation(self) -> Dict[str, Any]:
        """Fallback recommendation when system fails."""
        return {
            "action": {"type": "noop", "target": None},
            "impact": 0.0,
            "was_necessary": False,
            "confidence": 0.1,
            "explanation": "System using fallback mode - no action recommended.",
            "evaluated_actions": [
                {
                    "action": {"type": "noop", "target": None},
                    "label": "NOOP",
                    "impact": 0.0,
                    "necessary": False
                }
            ],
            "reasoning": {
                "best_action": "NOOP",
                "confidence": 0.1,
                "impact": 0.0,
                "was_necessary": False,
                "alternative_actions": [{
                    "action": {"type": "noop", "target": None},
                    "label": "NOOP",
                    "impact": 0.0,
                    "necessary": False,
                }],
                "explanation": "System using fallback mode - no action recommended.",
                "agent_name": get_current_agent_name(),
                "agent_action": "NOOP",
                "agent_action_impact": 0.0,
                "agent_action_rank": 1,
                "agent_action_matches_best": True,
            }
        }
