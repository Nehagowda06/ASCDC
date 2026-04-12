from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict, List, Mapping, Tuple

from env.environment import ASCDCEnvironment


class SmartAgent:
    """Horizon-based rollout planning agent for ASCDC environment.
    
    Evaluates 2-step action sequences through environment simulation to select
    best action considering delayed effects. Includes proactive drift detection,
    emergency mode for firestorms, and planned action sequences.
    """
    PERSISTENT_QUEUE_THRESHOLD = 4
    requires_env = True

    def __init__(self, horizon: int = 10):
        """Initialize agent with planning horizon.
        
        Args:
            horizon: Number of steps to simulate for sequence evaluation
        """
        self.base_horizon = max(1, int(horizon))
        self.horizon = self.base_horizon
        self._queue_persistence: Dict[str, int] = {queue: 0 for queue in ("A", "B", "C")}
        self._last_timestep = -1
        self.proactive_mode = False
        self.last_action: Dict[str, Any] | None = None
        self.planned_actions: List[Dict[str, Any]] = []

        self.firestorm_threshold = 2.0
        self.extreme_firestorm_threshold = 3.5
        self.emergency_horizon_boost = 8
        self.consecutive_firestorm_steps = 0
        self.target_focus = 2
        self.collapse_prevention_threshold = 4.5  # Critical: prevent system collapse

    def act(self, env: Any) -> Dict[str, Any]:
        """Select best action via sequence evaluation and planning.
        
        Evaluates candidate action sequences, applies pressure-aware thresholds,
        and manages planned action queue. Includes proactive drift detection and
        emergency mode for high-pressure scenarios.
        
        Args:
            env: Environment instance
            
        Returns:
            Action dict with 'type' and 'target' keys
        """
        snapshot = self._normalize_observation(env)
        self._update_queue_persistence(snapshot)
        self._update_proactive_mode(snapshot)

        system_pressure = float(snapshot.get("system_pressure", 0.0))
        is_firestorm = system_pressure > self.firestorm_threshold
        is_extreme_firestorm = system_pressure > self.extreme_firestorm_threshold
        is_collapse_risk = system_pressure > self.collapse_prevention_threshold

        if is_extreme_firestorm:
            self.horizon = self.base_horizon + self.emergency_horizon_boost
            self.consecutive_firestorm_steps += 1
        elif is_firestorm:
            self.horizon = self.base_horizon + 4
            self.consecutive_firestorm_steps += 1
        else:
            self.horizon = self.base_horizon
            self.consecutive_firestorm_steps = 0

        # CRITICAL: Prevent system collapse by forcing action in extreme conditions
        if is_collapse_risk:
            highest_queue = self._highest_queue(snapshot)
            return {"type": "restart", "target": highest_queue}

        if sum(float(value or 0.0) for value in snapshot.get("queues", {}).values()) < 0.1:
            action = {"type": "noop", "target": None}
            self.last_action = action
            return action

        if not is_extreme_firestorm and self._is_stable_noop_state(snapshot):
            action = {"type": "noop", "target": None}
            self.last_action = action
            self.planned_actions = []
            return action

        planned_action = self._next_planned_action(snapshot)
        if planned_action is not None:
            self.last_action = planned_action
            return planned_action

        if not is_firestorm:
            proactive_action = self._proactive_action(snapshot)
            if proactive_action is not None:
                self.last_action = proactive_action
                self.planned_actions = []
                return proactive_action

        best_sequence: List[Dict[str, Any]] | None = None
        best_score = float("-inf")
        noop_score = float("-inf")

        for sequence in self._candidate_sequences(snapshot):
            first_action = sequence[0]
            score = self._evaluate_sequence(env, snapshot, sequence)

            if self.last_action is not None and first_action["type"] != "noop":
                if (
                    first_action["type"] != self.last_action.get("type")
                    and first_action.get("target") != self.last_action.get("target")
                ):
                    score -= 0.03 if is_firestorm else 0.1

            if first_action["type"] == "noop":
                noop_score = max(noop_score, score)

            if score > best_score:
                best_score = score
                best_sequence = sequence

        action_threshold = 0.12 if is_extreme_firestorm else 0.18 if is_firestorm else 0.35
        if (
            best_sequence is not None
            and best_sequence[0]["type"] != "noop"
            and best_score < noop_score + action_threshold
        ):
            selected_action = {"type": "noop", "target": None}
        else:
            selected_action = deepcopy(best_sequence[0]) if best_sequence else {"type": "noop", "target": None}

        self.last_action = selected_action
        self.planned_actions = [
            deepcopy(action)
            for action in (best_sequence or [])[1:]
            if action["type"] != "noop"
        ]
        return selected_action

    def _evaluate_sequence(
        self,
        env: Any,
        observation: Dict[str, Any],
        actions: List[Dict[str, Any]],
    ) -> float:
        """Evaluate action sequence through environment simulation.
        
        Simulates sequence for horizon steps with 0.85 discount factor.
        Applies pressure-based bonuses/penalties and instability penalties.
        
        Args:
            env: Environment instance
            observation: Current observation dict
            actions: Sequence of action dicts to evaluate
            
        Returns:
            Scalar score for the sequence
        """
        env_copy = self._clone_env(env)
        starting_pressure = float(observation.get("system_pressure", 0.0) or 0.0)
        total = 0.0
        discount = 1.0
        rejected_actions = 0

        for step_index in range(self.horizon):
            chosen_action = actions[step_index] if step_index < len(actions) else {"type": "noop", "target": None}
            _, reward, done, info = env_copy.step(chosen_action, evaluate_counterfactual=False)
            total += float(reward) * discount
            if info.get("action_rejected") and chosen_action["type"] != "noop":
                rejected_actions += 1
                total -= 1.25
            discount *= 0.85
            if done:
                break

        final_snapshot = self._normalize_observation(env_copy.state())
        final_pressure = float(final_snapshot.get("system_pressure", 0.0) or 0.0)
        final_instability = float(final_snapshot.get("instability_score", 0.0) or 0.0)
        final_ratios = self._queue_ratios(final_snapshot)
        max_ratio = max(final_ratios.values(), default=0.0)
        total_queue = sum(float(value or 0.0) for value in final_snapshot.get("queues", {}).values())

        first_action = actions[0]
        primary_target = self._highest_queue(observation)
        score = total

        if starting_pressure > 2.0 and first_action["type"] != "noop":
            score += 1.0
            if starting_pressure > 3.5:
                score += 0.5

        if starting_pressure > 2.0 and first_action["type"] == "throttle":
            score += 0.5

        if starting_pressure > 2.5 and first_action["type"] == "noop" and self.consecutive_firestorm_steps > 3:
            score -= 0.8

        if first_action.get("target") == primary_target and first_action["type"] != "noop":
            score += 0.35

        score += (starting_pressure - final_pressure) * 0.75
        score -= final_pressure * 1.25
        score -= final_instability * 1.5
        score -= max_ratio * 0.9
        score -= total_queue * 0.015
        score -= rejected_actions * 1.5
        return score

    def _proactive_action(self, observation: Dict[str, Any]) -> Dict[str, Any] | None:
        pressure = float(observation.get("system_pressure", 0.0) or 0.0)
        instability = float(observation.get("instability_score", 0.0) or 0.0)
        smoothed_drift = float(observation.get("smoothed_drift", observation.get("drift_score", 0.0)) or 0.0)
        pressure_delta = float(observation.get("pressure_delta", 0.0) or 0.0)
        highest_queue = self._highest_queue(observation)

        if pressure > 2.5 and instability > 0.8:
            if pressure > 3.5:
                return {"type": "restart", "target": highest_queue}
            return {"type": "throttle", "target": highest_queue}

        if pressure < 1.0 and instability > 0.3:
            return {"type": "throttle", "target": highest_queue}

        if (
            self.proactive_mode
            and self._queue_persistence.get(highest_queue, 0) > self.PERSISTENT_QUEUE_THRESHOLD
            and smoothed_drift > 0.1
            and pressure_delta >= 0.0
        ):
            if pressure > 1.8:
                return {"type": "scale", "target": highest_queue}
            return {"type": "throttle", "target": highest_queue}

        return None

    def _emergency_action(self, observation: Dict[str, Any]) -> Dict[str, Any] | None:
        system_pressure = float(observation.get("system_pressure", 0.0))
        instability = float(observation.get("instability_score", 0.0))
        critical_queue = self._highest_queue(observation)
        ranked_targets = self._ranked_targets(observation)
        secondary_target = ranked_targets[1][0] if len(ranked_targets) > 1 else critical_queue

        if system_pressure > 4.5 or instability > 2.5:
            return {"type": "restart", "target": critical_queue}
        if system_pressure > 3.8 or instability > 2.0:
            return {"type": "throttle", "target": critical_queue}
        if system_pressure > 3.2 and secondary_target != critical_queue:
            return {"type": "restart", "target": secondary_target}
        if system_pressure > 3.2:
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

    def _candidate_sequences(self, observation: Dict[str, Any]) -> List[List[Dict[str, Any]]]:
        ranked_targets = [
            queue
            for queue, _ in self._ranked_targets(observation)
            if self._is_action_available(observation, {"type": "restart", "target": queue})
        ][: self.target_focus]
        if not ranked_targets:
            return [[{"type": "noop", "target": None}]]

        sequences: List[List[Dict[str, Any]]] = []
        seen: set[Tuple[Tuple[str, str | None], ...]] = set()

        for action in self._get_possible_actions(observation):
            sequence = [deepcopy(action)]
            key = self._sequence_key(sequence)
            if key not in seen:
                sequences.append(sequence)
                seen.add(key)

            for followup in self._get_followup_actions(action, ranked_targets):
                sequence = [deepcopy(action), deepcopy(followup)]
                key = self._sequence_key(sequence)
                if key not in seen:
                    sequences.append(sequence)
                    seen.add(key)

        return sequences

    def _get_possible_actions(self, observation: Dict[str, Any]) -> List[Dict[str, Any]]:
        actions: List[Dict[str, Any]] = [{"type": "noop", "target": None}]
        for queue, _ in self._ranked_targets(observation):
            if not self._is_action_available(observation, {"type": "restart", "target": queue}):
                continue
            actions.extend([
                {"type": "restart", "target": queue},
                {"type": "scale", "target": queue},
                {"type": "throttle", "target": queue},
            ])
        return actions

    def _get_followup_actions(
        self,
        first_action: Dict[str, Any],
        ranked_targets: List[str],
    ) -> List[Dict[str, Any]]:
        followups: List[Dict[str, Any]] = [{"type": "noop", "target": None}]
        for target in ranked_targets:
            for action_type in ("restart", "scale", "throttle"):
                if (
                    target == first_action.get("target")
                    and first_action["type"] in {"restart", "scale"}
                ):
                    continue
                followups.append({"type": action_type, "target": target})
        return followups

    def _sequence_key(self, actions: List[Dict[str, Any]]) -> Tuple[Tuple[str, str | None], ...]:
        return tuple((action["type"], action.get("target")) for action in actions)

    def _highest_queue(self, observation: Dict[str, Any]) -> str:
        ranked = self._ranked_targets(observation)
        for queue, _ in ranked:
            if self._is_action_available(observation, {"type": "restart", "target": queue}):
                return queue
        return ranked[0][0] if ranked else "A"

    def _next_planned_action(self, observation: Dict[str, Any]) -> Dict[str, Any] | None:
        while self.planned_actions:
            action = deepcopy(self.planned_actions.pop(0))
            if self._is_action_available(observation, action):
                return action
        return None

    def _is_action_available(self, observation: Dict[str, Any], action: Dict[str, Any]) -> bool:
        if action["type"] == "noop":
            return True
        target = action.get("target")
        if not target:
            return False
        active_locks = observation.get("active_locks", {}) or {}
        return target not in active_locks

    def _queue_ratios(self, observation: Dict[str, Any]) -> Dict[str, float]:
        queues = observation.get("queues", {}) or {}
        capacities = observation.get("capacities", {}) or {}
        return {
            queue: float(queues.get(queue, 0.0) or 0.0) / max(float(capacities.get(queue, 1.0) or 1.0), 1.0)
            for queue in queues
        }

    def _ranked_targets(self, observation: Dict[str, Any]) -> List[Tuple[str, float]]:
        queues = observation.get("queues", {}) or {}
        capacities = observation.get("capacities", {}) or {}
        base_load = observation.get("base_load", {}) or {}
        latencies = observation.get("latencies", {}) or {}
        active_locks = observation.get("active_locks", {}) or {}
        pending_actions = observation.get("pending_actions", []) or []

        rankings: List[Tuple[str, float]] = []
        for queue in ("A", "B", "C"):
            queue_level = float(queues.get(queue, 0.0) or 0.0)
            capacity = max(float(capacities.get(queue, 1.0) or 1.0), 1.0)
            load_ratio = float(base_load.get(queue, 0.0) or 0.0) / capacity
            queue_ratio = queue_level / capacity
            latency = float(latencies.get(queue, 0.0) or 0.0)
            pending_support = sum(
                1.0
                for item in pending_actions
                if item.get("target") == queue and item.get("type") in {"scale", "restart", "throttle"}
            )
            lock_penalty = 4.0 if queue in active_locks else 0.0

            urgency = (
                (queue_ratio * 1.8)
                + (max(load_ratio - 1.0, 0.0) * 2.4)
                + (queue_level * 0.08)
                + (latency * 0.2)
                - (pending_support * 0.3)
                - lock_penalty
            )
            rankings.append((queue, urgency))

        rankings.sort(key=lambda item: item[1], reverse=True)
        return rankings

    def _update_queue_persistence(self, observation: Dict[str, Any]) -> None:
        timestep = int(observation.get("timestep", 0) or 0)
        if timestep <= self._last_timestep:
            self._queue_persistence = {queue: 0 for queue in ("A", "B", "C")}
            self.planned_actions = []

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
        elif hasattr(observation, "state") and callable(getattr(observation, "state")):
            snapshot = dict(observation.state())
        elif hasattr(observation, "__dict__"):
            snapshot = dict(vars(observation))
        else:
            snapshot = {}

        queues = snapshot.get("queues", {}) or {}
        capacities = snapshot.get("capacities", {}) or {}

        return {
            "queues": {str(queue): float(value or 0.0) for queue, value in queues.items()},
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
            except Exception:
                return deepcopy(env)

        raise TypeError("SmartAgent requires an ASCDCEnvironment-compatible object with clone().")


__all__ = ["SmartAgent"]
