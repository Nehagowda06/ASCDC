from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Mapping

from env.environment import ASCDCEnvironment


class SmartAgent:
    PERSISTENT_QUEUE_THRESHOLD = 4

<<<<<<< HEAD
    def __init__(self, horizon: int = 10):
=======
    def __init__(self, horizon: int = 12):
>>>>>>> 3f8b51ce07d34fbefba8a351d57cc42f33924908
        self.horizon = max(1, int(horizon))
        self._queue_persistence: Dict[str, int] = {queue: 0 for queue in ("A", "B", "C")}
        self._last_timestep = -1
        self.proactive_mode = False
        self.last_action: Dict[str, Any] | None = None
        self.action_cooldown = 0

    def act(self, env: Any) -> Dict[str, Any]:
        snapshot = self._normalize_observation(env)
        self._update_queue_persistence(snapshot)
        self._update_proactive_mode(snapshot)

        if self.action_cooldown > 0:
            self.action_cooldown -= 1
            action = {"type": "noop", "target": None}
            self.last_action = action
            return action

        if sum(float(value or 0.0) for value in snapshot.get("queues", {}).values()) < 0.1:
            action = {"type": "noop", "target": None}
            self.last_action = action
            return action

        if self._is_stable_noop_state(snapshot):
            action = {"type": "noop", "target": None}
            self.last_action = action
            return action

        proactive_action = self._proactive_action(snapshot)
        if proactive_action is not None:
            self.last_action = proactive_action
            self.action_cooldown = 2
            return proactive_action

        actions = self._get_possible_actions(snapshot)

        best_action: Dict[str, Any] | None = None
        best_score = float("-inf")
        noop_score = float("-inf")

        for action in actions:
            for followup in self._get_followup_actions(action):
                score = self._evaluate_sequence(env, snapshot, [action, followup])
                if self.last_action is not None and action["type"] != self.last_action["type"]:
                    score -= 0.15
                if action["type"] == "noop":
                    noop_score = max(noop_score, score)
                if score > best_score:
                    best_score = score
                    best_action = action

        if (
            best_action is not None
            and best_action["type"] != "noop"
            and best_score < noop_score + 0.4
        ):
            selected_action = {"type": "noop", "target": None}
        else:
            selected_action = best_action or {"type": "noop", "target": None}

        self.last_action = selected_action
        if selected_action["type"] != "noop":
            self.action_cooldown = 2

        return selected_action

    def _evaluate_sequence(
        self,
        env: Any,
        observation: Dict[str, Any],
        actions: List[Dict[str, Any]],
    ) -> float:
        env_copy = self._clone_env(env)

        total = 0.0
        discount = 1.0

        for step_index in range(self.horizon):
            chosen_action = actions[step_index] if step_index < len(actions) else {"type": "noop", "target": None}
            _, reward, done, _ = env_copy.step(chosen_action, evaluate_counterfactual=False)
            total += float(reward) * discount
            discount *= 0.85
            if done:
                break

        score = total
        pressure = float(observation.get("system_pressure", 0.0) or 0.0)
<<<<<<< HEAD
        first_action = actions[0]

        if pressure > 2.0 and first_action["type"] != "noop":
            score += 1.0

        if pressure < 1.0 and first_action["type"] != "noop":
            score -= 0.5

        if pressure > 2.0 and first_action["type"] == "throttle":
            score += 0.5
=======
        instability = float(observation.get("instability_score", 0.0) or 0.0)
        first_action = actions[0]

        # Reward action in high pressure, but let rollout decide
        if pressure > 2.0 and first_action["type"] != "noop":
            score += 0.8

        # Penalize inaction when instability is building
        if instability > 0.4 and first_action["type"] == "noop":
            score -= 0.4

        # Slight penalty for premature action in calm states
        if pressure < 0.8 and first_action["type"] != "noop":
            score -= 0.3
>>>>>>> 3f8b51ce07d34fbefba8a351d57cc42f33924908

        return score

    def _proactive_action(self, observation: Dict[str, Any]) -> Dict[str, Any] | None:
        pressure = float(observation.get("system_pressure", 0.0) or 0.0)
        instability = float(observation.get("instability_score", 0.0) or 0.0)
        smoothed_drift = float(observation.get("smoothed_drift", observation.get("drift_score", 0.0)) or 0.0)
        pressure_delta = float(observation.get("pressure_delta", 0.0) or 0.0)
        highest_queue = self._highest_queue(observation)

        if pressure < 1.0 and instability > 0.3:
            return {"type": "throttle", "target": highest_queue}

        if (
            self.proactive_mode
            and
            self._queue_persistence.get(highest_queue, 0) > self.PERSISTENT_QUEUE_THRESHOLD
            and smoothed_drift > 0.1
            and pressure_delta >= 0.0
        ):
            return {"type": "throttle", "target": highest_queue}

        return None

    def _update_proactive_mode(self, observation: Dict[str, Any]) -> None:
        smoothed_drift = float(observation.get("smoothed_drift", observation.get("drift_score", 0.0)) or 0.0)
        if smoothed_drift > 0.15:
            self.proactive_mode = True
        elif smoothed_drift < 0.05:
            self.proactive_mode = False

    def _is_stable_noop_state(self, observation: Dict[str, Any]) -> bool:
        pressure = float(observation.get("system_pressure", 0.0) or 0.0)
        smoothed_drift = float(observation.get("smoothed_drift", observation.get("drift_score", 0.0)) or 0.0)
        queues = observation.get("queues", {}) or {}
        return (
            pressure < 0.4
            and smoothed_drift < 0.03
            and all(float(value or 0.0) < 0.05 for value in queues.values())
        )

    def _get_possible_actions(self, obs: Dict[str, Any]) -> List[Dict[str, Any]]:
        actions: List[Dict[str, Any]] = [{"type": "noop", "target": None}]
        for queue in ["A", "B", "C"]:
            actions.extend([
                {"type": "restart", "target": queue},
                {"type": "scale", "target": queue},
                {"type": "throttle", "target": queue},
            ])
        return actions

    def _get_followup_actions(self, action: Dict[str, Any]) -> List[Dict[str, Any]]:
        followups: List[Dict[str, Any]] = [{"type": "noop", "target": None}]
        target = action.get("target")
        if target:
            followups.append({"type": "throttle", "target": target})
        return followups

    def _highest_queue(self, observation: Dict[str, Any]) -> str:
        queues = observation.get("queues", {}) or {}
        return max(
            queues,
            key=lambda queue: float(queues.get(queue, 0.0) or 0.0),
            default="A",
        )

    def _update_queue_persistence(self, observation: Dict[str, Any]) -> None:
        timestep = int(observation.get("timestep", 0) or 0)
        if timestep <= self._last_timestep:
            self._queue_persistence = {queue: 0 for queue in ("A", "B", "C")}

        queues = observation.get("queues", {}) or {}
        for queue in ("A", "B", "C"):
            level = float(queues.get(queue, 0.0) or 0.0)
            if level > 0.0:
                self._queue_persistence[queue] = self._queue_persistence.get(queue, 0) + 1
            else:
                self._queue_persistence[queue] = 0

        self._last_timestep = timestep

    def _normalize_observation(self, observation: Any) -> Dict[str, Any]:
        if isinstance(observation, Mapping):
            snapshot = dict(observation)
        elif hasattr(observation, "__dict__"):
            snapshot = dict(vars(observation))
        else:
            snapshot = {}

        queues = snapshot.get("queues", {}) or {}
        capacities = snapshot.get("capacities", {}) or {}

        return {
            "queues": {
                str(queue): float(value or 0.0)
                for queue, value in queues.items()
            },
            "capacities": {
                str(queue): max(float(value or 0.0), 1.0)
                for queue, value in capacities.items()
            },
            "system_pressure": float(snapshot.get("system_pressure", snapshot.get("pressure", 0.0)) or 0.0),
            "instability_score": float(snapshot.get("instability_score", 0.0) or 0.0),
            "drift_score": float(snapshot.get("drift_score", 0.0) or 0.0),
            "smoothed_drift": float(snapshot.get("smoothed_drift", snapshot.get("drift_score", 0.0)) or 0.0),
            "retry_rate": float(snapshot.get("retry_rate", 0.0) or 0.0),
            "error_rate": float(snapshot.get("error_rate", 0.0) or 0.0),
            "remaining_budget": float(snapshot.get("remaining_budget", snapshot.get("budget", 100.0)) or 0.0),
            "latencies": {
                str(queue): float(value or 0.0)
                for queue, value in (snapshot.get("latencies", {}) or {}).items()
            },
            "latency": float(snapshot.get("latency", 0.0) or 0.0),
            "pressure_delta": float(snapshot.get("pressure_delta", 0.0) or 0.0),
            "latency_delta": float(snapshot.get("latency_delta", 0.0) or 0.0),
            "timestep": int(snapshot.get("timestep", 0) or 0),
            "pending_effects": deepcopy(snapshot.get("pending_effects", []) or []),
            "pending_actions": deepcopy(snapshot.get("pending_actions", []) or []),
            "active_locks": deepcopy(snapshot.get("active_locks", {}) or {}),
            "base_load": {
                str(queue): float(value or 0.0)
                for queue, value in (snapshot.get("base_load", {}) or {}).items()
            },
            "load_schedule": deepcopy(snapshot.get("load_schedule", {}) or {}),
            "noop_streak": int(snapshot.get("noop_streak", 0) or 0),
        }

    def _clone_env(self, env: Any) -> ASCDCEnvironment:
        if hasattr(env, "clone"):
            cloned = env.clone()
            if isinstance(cloned, ASCDCEnvironment):
                return cloned

        if isinstance(env, ASCDCEnvironment):
            return env.clone()

        raise TypeError("SmartAgent requires an ASCDCEnvironment-compatible object with clone().")


__all__ = ["SmartAgent"]
