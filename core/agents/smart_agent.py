from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Mapping

from env.environment import ASCDCEnvironment


class SmartAgent:
    PERSISTENT_QUEUE_THRESHOLD = 4
    requires_env = True

    def __init__(self, horizon: int = 10):
        self.base_horizon = max(1, int(horizon))
        self.horizon = self.base_horizon
        self._queue_persistence: Dict[str, int] = {queue: 0 for queue in ("A", "B", "C")}
        self._last_timestep = -1
        self.proactive_mode = False
        self.last_action: Dict[str, Any] | None = None
        self.action_cooldown = 0
        
        # Firestorm enhancements
        self.firestorm_threshold = 2.0  # System pressure threshold for firestorm detection
        self.extreme_firestorm_threshold = 3.5  # Extreme firestorm threshold
        self.emergency_horizon_boost = 8  # Additional planning steps in firestorm
        self.aggressive_action_bonus = 1.5  # Score bonus for aggressive actions in firestorm
        self.consecutive_firestorm_steps = 0  # Track firestorm duration

    def act(self, env: Any) -> Dict[str, Any]:
        snapshot = self._normalize_observation(env)
        self._update_queue_persistence(snapshot)
        self._update_proactive_mode(snapshot)
        
        # Detect firestorm conditions
        system_pressure = float(snapshot.get("system_pressure", 0.0))
        instability = float(snapshot.get("instability_score", 0.0))
        is_firestorm = system_pressure > self.firestorm_threshold
        is_extreme_firestorm = system_pressure > self.extreme_firestorm_threshold
        
        # Adjust planning horizon for firestorm
        if is_extreme_firestorm:
            self.horizon = self.base_horizon + self.emergency_horizon_boost
            self.consecutive_firestorm_steps += 1
        elif is_firestorm:
            self.horizon = self.base_horizon + 4
            self.consecutive_firestorm_steps += 1
        else:
            self.horizon = self.base_horizon
            self.consecutive_firestorm_steps = 0

        if self.action_cooldown > 0:
            self.action_cooldown -= 1
            action = {"type": "noop", "target": None}
            self.last_action = action
            return action

        if sum(float(value or 0.0) for value in snapshot.get("queues", {}).values()) < 0.1:
            action = {"type": "noop", "target": None}
            self.last_action = action
            return action

        # Override stable state check in extreme firestorm
        if not is_extreme_firestorm and self._is_stable_noop_state(snapshot):
            action = {"type": "noop", "target": None}
            self.last_action = action
            return action

        # Enhanced proactive action for firestorm
        proactive_action = self._proactive_action(snapshot)
        if proactive_action is not None:
            self.last_action = proactive_action
            self.action_cooldown = 1 if is_firestorm else 2  # Shorter cooldown in firestorm
            return proactive_action

        # Emergency action override for extreme firestorm
        if is_extreme_firestorm:
            emergency_action = self._emergency_action(snapshot)
            if emergency_action:
                self.last_action = emergency_action
                self.action_cooldown = 1
                return emergency_action

        actions = self._get_possible_actions(snapshot)

        best_action: Dict[str, Any] | None = None
        best_score = float("-inf")
        noop_score = float("-inf")

        for action in actions:
            for followup in self._get_followup_actions(action):
                score = self._evaluate_sequence(env, snapshot, [action, followup])
                
                # Firestorm scoring adjustments
                if is_firestorm:
                    if action["type"] in ["restart", "scale"]:
                        score += self.aggressive_action_bonus
                    elif action["type"] == "noop" and system_pressure > 2.5:
                        score -= 1.0  # Penalize noop in firestorm
                        
                if self.last_action is not None and action["type"] != self.last_action["type"]:
                    score -= 0.05 if is_firestorm else 0.15  # Reduced switching penalty in firestorm
                    
                if action["type"] == "noop":
                    noop_score = max(noop_score, score)
                if score > best_score:
                    best_score = score
                    best_action = action

        # Lower threshold for action in firestorm
        action_threshold = 0.2 if is_firestorm else 0.4
        if (
            best_action is not None
            and best_action["type"] != "noop"
            and best_score < noop_score + action_threshold
        ):
            selected_action = {"type": "noop", "target": None}
        else:
            selected_action = best_action or {"type": "noop", "target": None}

        self.last_action = selected_action
        if selected_action["type"] != "noop":
            self.action_cooldown = 1 if is_firestorm else 2

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
        first_action = actions[0]

        # Enhanced scoring for firestorm scenarios
        if pressure > 2.0 and first_action["type"] != "noop":
            score += 1.0
            if pressure > 3.5:  # Extreme firestorm bonus
                score += 0.5
                if first_action["type"] in ["restart", "scale"]:
                    score += 0.3

        if pressure < 1.0 and first_action["type"] != "noop":
            score -= 0.5

        if pressure > 2.0 and first_action["type"] == "throttle":
            score += 0.5
            if pressure > 3.0:  # Extra bonus for throttle in high pressure
                score += 0.2
                
        # Penalty for inaction in prolonged firestorm
        if pressure > 2.5 and first_action["type"] == "noop" and self.consecutive_firestorm_steps > 3:
            score -= 0.8

        return score

    def _proactive_action(self, observation: Dict[str, Any]) -> Dict[str, Any] | None:
        pressure = float(observation.get("system_pressure", 0.0) or 0.0)
        instability = float(observation.get("instability_score", 0.0) or 0.0)
        smoothed_drift = float(observation.get("smoothed_drift", observation.get("drift_score", 0.0)) or 0.0)
        pressure_delta = float(observation.get("pressure_delta", 0.0) or 0.0)
        highest_queue = self._highest_queue(observation)

        # Enhanced proactive logic for firestorm scenarios
        if pressure > 2.5 and instability > 0.8:
            # Emergency proactive action in firestorm
            if pressure > 3.5:
                return {"type": "restart", "target": highest_queue}
            else:
                return {"type": "scale", "target": highest_queue}
                
        if pressure < 1.0 and instability > 0.3:
            return {"type": "throttle", "target": highest_queue}

        if (
            self.proactive_mode
            and
            self._queue_persistence.get(highest_queue, 0) > self.PERSISTENT_QUEUE_THRESHOLD
            and smoothed_drift > 0.1
            and pressure_delta >= 0.0
        ):
            # More aggressive action in high pressure
            if pressure > 1.8:
                return {"type": "scale", "target": highest_queue}
            else:
                return {"type": "throttle", "target": highest_queue}

        return None

    def _emergency_action(self, observation: Dict[str, Any]) -> Dict[str, Any] | None:
        """Emergency action logic for extreme firestorm scenarios."""
        queues = observation.get("queues", {}) or {}
        system_pressure = float(observation.get("system_pressure", 0.0))
        instability = float(observation.get("instability_score", 0.0))
        
        # Find most critical queue
        critical_queue = self._highest_queue(observation)
        
        # Extreme emergency response
        if system_pressure > 4.5 or instability > 2.5:
            # Catastrophic firestorm - immediate restart on critical queue
            return {"type": "restart", "target": critical_queue}
        elif system_pressure > 3.8 or instability > 2.0:
            # Severe firestorm - scale critical queue
            return {"type": "scale", "target": critical_queue}
        elif system_pressure > 3.2:
            # High firestorm - throttle critical queue aggressively
            return {"type": "throttle", "target": critical_queue}
        
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
            try:
                return env.clone()
            except Exception as e:
                print(f"[ERROR] {e}")
                # Fallback: use deepcopy if clone fails
                from copy import deepcopy
                return deepcopy(env)

        raise TypeError("SmartAgent requires an ASCDCEnvironment-compatible object with clone().")


__all__ = ["SmartAgent"]
