"""
CounterfactualPlannerAgent — strong decision-making agent for ASCDC.

Strategy:
- Reads all available env signals (pressure, instability, drift, queues, locks, budget)
- Derives the current operational regime from those signals
- In stable regimes: restraint (noop) is rewarded, so we default to noop
- In degrading/critical regimes: sample targeted candidates and pick the one
  with the highest counterfactual_impact over the evaluation horizon
- Memory penalty discourages repeating actions that previously had zero/negative impact
- Budget awareness: never attempt actions we cannot afford
- Lock awareness: never waste a candidate slot on a locked target
"""

from __future__ import annotations

import random
from copy import deepcopy
from typing import Any, Dict, List, Optional

from core.counterfactual import CounterfactualEvaluator


# Action costs mirror env.ACTION_COSTS so we can pre-filter unaffordable actions
_ACTION_COSTS: Dict[str, float] = {
    "noop": 0.0,
    "restart": 3.0,
    "scale": 5.0,
    "throttle": 2.0,
}


class CounterfactualPlannerAgent:
    """
    Regime-aware counterfactual planner.

    Regimes (derived from live env signals):
        stable      → pressure < 0.8 and instability < 0.15 and drift < 0.08
        degrading   → pressure 0.8–1.8 or instability 0.15–0.5 or drift 0.08–0.2
        critical    → pressure > 1.8 or instability > 0.5 or drift > 0.2

    In stable regime we return noop immediately (restraint is rewarded by the env).
    In degrading/critical we evaluate up to max_candidates actions and pick the best.
    """

    TARGETS = ("A", "B", "C")
    ACTION_TYPES = ("scale", "restart", "throttle")

    # Regime thresholds — tuned for ASCDC's 3 tasks
    # T1 Firestorm: base_load A=30 vs cap A=20 → pressure spikes fast, need early trigger
    # T2 Slow Leak: gradual drift, catch it before collapse
    # T3 Ghost Spike: short surge, don't overreact after it subsides
    STABLE_PRESSURE = 0.5       # tighter: act earlier
    CRITICAL_PRESSURE = 1.2     # lower: escalate sooner on T1
    STABLE_INSTABILITY = 0.10
    CRITICAL_INSTABILITY = 0.35
    STABLE_DRIFT = 0.05
    CRITICAL_DRIFT = 0.15

    def __init__(self, env: Any, max_candidates: int = 6, seed: int = 42):
        self.env = env
        self.max_candidates = max_candidates
        self.evaluator = CounterfactualEvaluator()
        self.rng = random.Random(seed)
        # history: list of (action_key, impact) to penalise repeated bad actions
        self._history: List[tuple[str, float]] = []
        self._max_history = 60
        self._last_action_type: Optional[str] = None
        self._steps_since_action: int = 0

    # ------------------------------------------------------------------ #
    #  Public interface                                                    #
    # ------------------------------------------------------------------ #

    def act(self, env: Any) -> Dict[str, Any]:
        """Select the best action given the current environment state."""
        self.env = env
        snapshot = self._snapshot(env)
        regime = self._regime(snapshot)

        if regime == "stable":
            self._steps_since_action += 1
            return {"type": "noop", "target": None}

        # If pressure is rising fast and we haven't acted in a while, be more aggressive
        pressure = snapshot["system_pressure"]
        noop_streak = snapshot.get("noop_streak", self._steps_since_action)
        if noop_streak > 3 and pressure > self.STABLE_PRESSURE:
            regime = "critical"  # escalate to ensure we act

        candidates = self._build_candidates(snapshot, regime)
        best_action = self._evaluate_candidates(env, candidates, snapshot)

        key = self._action_key(best_action)
        self._history.append((key, 0.0))
        if len(self._history) > self._max_history:
            self._history.pop(0)

        if best_action["type"] != "noop":
            self._last_action_type = best_action["type"]
            self._steps_since_action = 0
        else:
            self._steps_since_action += 1

        return best_action

    # ------------------------------------------------------------------ #
    #  Regime detection                                                    #
    # ------------------------------------------------------------------ #

    def _regime(self, snapshot: Dict[str, Any]) -> str:
        pressure = snapshot["system_pressure"]
        instability = snapshot["instability_score"]
        drift = snapshot["smoothed_drift"]

        if (
            pressure >= self.CRITICAL_PRESSURE
            or instability >= self.CRITICAL_INSTABILITY
            or drift >= self.CRITICAL_DRIFT
        ):
            return "critical"

        if (
            pressure >= self.STABLE_PRESSURE
            or instability >= self.STABLE_INSTABILITY
            or drift >= self.STABLE_DRIFT
        ):
            return "degrading"

        return "stable"

    # ------------------------------------------------------------------ #
    #  Candidate generation                                                #
    # ------------------------------------------------------------------ #

    def _build_candidates(
        self, snapshot: Dict[str, Any], regime: str
    ) -> List[Dict[str, Any]]:
        """
        Build a targeted, affordable, unlocked candidate list.
        Always includes noop as a fallback.
        Prioritises the single worst queue to maintain action consistency
        (reduces oscillation penalty in the grader's smoothness score).
        """
        budget = snapshot["remaining_budget"]
        active_locks = snapshot["active_locks"]
        queues = snapshot["queues"]
        capacities = snapshot["capacities"]

        # Rank targets by queue-to-capacity ratio (worst first)
        ratios = {
            t: queues.get(t, 0.0) / max(capacities.get(t, 1.0), 1.0)
            for t in self.TARGETS
        }
        ranked_targets = sorted(self.TARGETS, key=lambda t: ratios[t], reverse=True)

        candidates: List[Dict[str, Any]] = [{"type": "noop", "target": None}]

        # Focus on the single worst unlocked target first (consistency > coverage)
        primary_target: Optional[str] = None
        for t in ranked_targets:
            if not self._is_locked(t, active_locks, snapshot["timestep"]):
                primary_target = t
                break

        if primary_target is not None:
            for action_type in self._action_priority(regime, ratios[primary_target]):
                cost = _ACTION_COSTS.get(action_type, 0.0)
                if budget >= cost:
                    candidates.append({"type": action_type, "target": primary_target})

        # Fill remaining slots with other targets
        for target in ranked_targets:
            if target == primary_target:
                continue
            if self._is_locked(target, active_locks, snapshot["timestep"]):
                continue
            for action_type in self._action_priority(regime, ratios[target]):
                cost = _ACTION_COSTS.get(action_type, 0.0)
                if budget < cost:
                    continue
                candidates.append({"type": action_type, "target": target})
                break  # one action type per secondary target

        return candidates[: self.max_candidates]

    def _action_priority(self, regime: str, queue_ratio: float) -> List[str]:
        """Return action types ordered by suitability for the regime."""
        if regime == "critical":
            if queue_ratio >= 2.0:
                return ["restart", "scale", "throttle"]
            return ["scale", "throttle", "restart"]
        # degrading
        if queue_ratio >= 1.0:
            return ["scale", "throttle", "restart"]
        return ["throttle", "scale", "restart"]

    # ------------------------------------------------------------------ #
    #  Candidate evaluation                                                #
    # ------------------------------------------------------------------ #

    def _evaluate_candidates(
        self,
        env: Any,
        candidates: List[Dict[str, Any]],
        snapshot: Dict[str, Any],
    ) -> Dict[str, Any]:
        best_action: Dict[str, Any] = {"type": "noop", "target": None}
        best_score = float("-inf")
        noop_score = float("-inf")

        scored_candidates = []
        for action in candidates:
            try:
                cf = self.evaluator.evaluate(env, action)
                impact = float(cf.get("counterfactual_impact", 0.0))
                necessary = bool(cf.get("was_action_necessary", False))
            except Exception:
                impact = 0.0
                necessary = False

            penalty = self._memory_penalty(action)
            score = impact - penalty

            # Smoothness bonus: prefer same action type as last to reduce oscillation
            if (
                self._last_action_type is not None
                and action["type"] != "noop"
                and action["type"] == self._last_action_type
            ):
                score += 0.08

            # Slight bonus for actions that are flagged as necessary
            if necessary:
                score += 0.1

            scored_candidates.append((score, impact, action))

            if action["type"] == "noop":
                noop_score = score
            elif score > best_score:
                best_score = score
                best_action = action

        # Heuristic fallback: if no non-noop candidate clearly beats noop,
        # use adaptive heuristic to decide (mirrors simple-adaptive logic)
        if best_score <= noop_score + 0.05:
            heuristic = self._adaptive_heuristic(snapshot)
            if heuristic["type"] != "noop":
                # Verify heuristic action is affordable and unlocked
                cost = _ACTION_COSTS.get(heuristic["type"], 0.0)
                locked = self._is_locked(
                    heuristic.get("target", ""),
                    snapshot["active_locks"],
                    snapshot["timestep"],
                )
                if snapshot["remaining_budget"] >= cost and not locked:
                    return deepcopy(heuristic)
            return {"type": "noop", "target": None}

        # Only return a non-noop action if it genuinely beats noop
        threshold = -0.05
        if best_action["type"] != "noop" and best_score <= threshold:
            return {"type": "noop", "target": None}

        return deepcopy(best_action)

    def _adaptive_heuristic(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        """Mirrors simple-adaptive logic as a fallback when CF scores are ambiguous."""
        queues = snapshot["queues"]
        capacities = snapshot["capacities"]
        pressure = snapshot["system_pressure"]
        retry = snapshot["retry_rate"]
        error = snapshot["error_rate"]

        ratios = {
            t: queues.get(t, 0.0) / max(capacities.get(t, 1.0), 1.0)
            for t in self.TARGETS
        }
        max_ratio = max(ratios.values(), default=0.0)
        target = max(ratios, key=ratios.get, default="A")

        if max_ratio >= 2.0 or pressure >= 2.2:
            return {"type": "restart", "target": target}
        if max_ratio >= 0.95 or pressure >= 1.0:
            return {"type": "scale", "target": target}
        if max_ratio >= 0.65 and (retry >= 0.35 or error >= 0.25):
            return {"type": "throttle", "target": target}
        return {"type": "noop", "target": None}

    # ------------------------------------------------------------------ #
    #  Memory penalty                                                      #
    # ------------------------------------------------------------------ #

    def _memory_penalty(self, action: Dict[str, Any]) -> float:
        key = self._action_key(action)
        bad_repeats = sum(
            1 for k, impact in self._history
            if k == key and impact <= 0.0
        )
        return bad_repeats * 0.12

    # ------------------------------------------------------------------ #
    #  Helpers                                                             #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _is_locked(
        target: str,
        active_locks: Dict[str, Any],
        timestep: int,
    ) -> bool:
        unlock_at = active_locks.get(target)
        if unlock_at is None:
            return False
        return int(timestep) < int(unlock_at)

    @staticmethod
    def _action_key(action: Dict[str, Any]) -> str:
        return f"{action.get('type', 'noop')}:{action.get('target', 'none')}"

    @staticmethod
    def _snapshot(env: Any) -> Dict[str, Any]:
        """Extract a normalised snapshot from the env object."""
        if hasattr(env, "state") and callable(env.state):
            raw = env.state()
        elif hasattr(env, "__dict__"):
            raw = vars(env)
        else:
            raw = {}

        queues = raw.get("queues", {}) or {}
        capacities = raw.get("capacities", {}) or {}

        return {
            "queues": {k: float(v or 0.0) for k, v in queues.items()},
            "capacities": {k: max(float(v or 0.0), 1.0) for k, v in capacities.items()},
            "system_pressure": float(raw.get("system_pressure", raw.get("pressure", 0.0)) or 0.0),
            "instability_score": float(raw.get("instability_score", 0.0) or 0.0),
            "smoothed_drift": float(raw.get("smoothed_drift", raw.get("drift_score", 0.0)) or 0.0),
            "remaining_budget": float(raw.get("remaining_budget", 100.0) or 0.0),
            "active_locks": dict(raw.get("active_locks", {}) or {}),
            "timestep": int(raw.get("timestep", 0) or 0),
            "retry_rate": float(raw.get("retry_rate", 0.0) or 0.0),
            "error_rate": float(raw.get("error_rate", 0.0) or 0.0),
        }


__all__ = ["CounterfactualPlannerAgent"]
