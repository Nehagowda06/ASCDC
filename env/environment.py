from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import logging
import math
import random

from core.evaluation_metrics import evaluate_step_metrics

logger = logging.getLogger(__name__)

COUNTERFACTUAL_HORIZON = 7


@dataclass
class Action:
    type: str = "noop"
    target: Optional[str] = None
    magnitude: float = 1.0


@dataclass
class Observation:
    queues: Dict[str, float]
    capacities: Dict[str, float]
    latencies: Dict[str, float]
    latency: float
    retry_rate: float
    error_rate: float
    remaining_budget: float
    system_pressure: float
    timestep: int
    done: bool
    pending_actions: List[Dict[str, Any]]


class ASCDCEnvironment:
    COUNTERFACTUAL_HORIZON = COUNTERFACTUAL_HORIZON
    QUEUE_ORDER = ("A", "B", "C")

    DEFAULT_CAPACITIES = {"A": 16.0, "B": 14.0, "C": 12.0}
    DEFAULT_LATENCIES = {"A": 1.2, "B": 1.6, "C": 2.1}
    DEFAULT_BASE_LOAD = {"A": 18.0, "B": 5.0, "C": 3.0}
    ACTION_COSTS = {"noop": 0.0, "restart": 3.0, "scale": 5.0, "throttle": 2.0}
    ACTION_LOCK_DURATIONS = {"restart": 2, "scale": 3}
    ACTION_REJECTION_PENALTY = 0.4
    INSTABILITY_PRESSURE_THRESHOLD = 1.25
    INSTABILITY_RESET_DELTA = 0.15
    INSTABILITY_GROWTH_RATE = 0.45
    STABLE_NOOP_PRESSURE_THRESHOLD = 0.75
    STABLE_NOOP_QUEUE_THRESHOLD = 0.35
    NOOP_STABLE_BONUS = 0.03
    NOOP_UNSTABLE_PENALTY = 0.08

    SCALE_DELAY = 3
    RESTART_DELAY = 2
    THROTTLE_DELAY = 1

    def __init__(self, seed: Optional[int] = 0, max_timesteps: int = 50):
        self.seed = seed
        self.rng = random.Random(seed)

        self.default_max_timesteps = max_timesteps
        self.max_timesteps = max_timesteps

        self.capacities = deepcopy(self.DEFAULT_CAPACITIES)
        self.base_latencies = deepcopy(self.DEFAULT_LATENCIES)
        self.base_load = deepcopy(self.DEFAULT_BASE_LOAD)

        self.reset(seed=seed)

    def reset(self, seed: Optional[int] = None, config: Optional[Dict[str, Any]] = None) -> Observation:
        assert self.COUNTERFACTUAL_HORIZON > 0
        reset_seed = seed
        if reset_seed is None and config:
            reset_seed = config.get("seed")
        if reset_seed is not None:
            self.seed = reset_seed
            self.rng = random.Random(reset_seed)

        # Always rebuild from a clean default state so task config and delayed effects do not leak.
        self.queues = {queue: 0.0 for queue in self.QUEUE_ORDER}
        self.capacities = deepcopy(self.DEFAULT_CAPACITIES)
        self.base_load = deepcopy(self.DEFAULT_BASE_LOAD)
        self.max_timesteps = self.default_max_timesteps
        self.load_schedule: Dict[int, Dict[str, float]] = {}
        self.pending_effects: List[Dict[str, Any]] = []
        assert isinstance(self.pending_effects, list)
        self._due_effects_this_step: List[Dict[str, Any]] = []
        self._throttle_effects = {}
        self._latency_spikes: Dict[str, float] = {}
        self._retry_spike = 0.0
        self._instability_penalty = 0.0
        self.active_locks: Dict[str, int] = {}
        self.logs: List[Dict[str, Any]] = []

        if config:
            if "base_load" in config:
                self.base_load.update(config["base_load"])
            if "capacities" in config:
                self.capacities.update(config["capacities"])
            if "initial_queues" in config:
                self.queues.update(config["initial_queues"])
            if "initial_budget" in config:
                self.remaining_budget = float(config["initial_budget"])
            else:
                self.remaining_budget = 100.0
            if "max_timesteps" in config:
                self.max_timesteps = int(config["max_timesteps"])
            self.load_schedule = deepcopy(config.get("load_schedule", {}))
        else:
            self.remaining_budget = 100.0

        self.latencies = deepcopy(self.base_latencies)
        self.retry_rate = 0.08
        self.error_rate = 0.02
        self.system_pressure = 0.0
        self.instability_score = 0.0
        self.drift_score = 0.0
        self.smoothed_drift = 0.0
        self.steps_since_action = 0
        self.noop_streak = 0
        self.last_action_type: Optional[str] = None
        self._last_counterfactual = 0.0
        self.prev_pressure = 0.0
        self.prev_latency = sum(self.latencies.values()) / len(self.latencies)
        self.pressure_delta = 0.0
        self.latency_delta = 0.0
        self.timestep = 0
        self._cf_active = False

        return self._build_observation()

    def step(self, action: Action, evaluate_counterfactual: bool = True):
        assert self.timestep >= 0
        self._process_pending_effects()
        self._expire_action_locks()

        normalized_action = self._normalize_action(action)

        if self._cf_active:
            evaluate_counterfactual = False

        actual_cumulative_reward = 0.0
        noop_cumulative_reward = 0.0
        counterfactual_impact = 0.0

        if evaluate_counterfactual:
            self._cf_active = True
            try:
                action_env = self._clone_for_rollout()
                noop_env = self._clone_for_rollout()
                actual_cumulative_reward = self._rollout_cumulative_reward(
                    action_env,
                    normalized_action,
                    COUNTERFACTUAL_HORIZON,
                )
                noop_cumulative_reward = self._rollout_cumulative_reward(
                    noop_env,
                    {"type": "noop", "target": None},
                    COUNTERFACTUAL_HORIZON,
                )
                counterfactual_impact = actual_cumulative_reward - noop_cumulative_reward
            finally:
                self._cf_active = False

        observation, actual_reward, done, info = self._execute_step(normalized_action)

        if counterfactual_impact > 0:
            final_reward = actual_reward + (0.3 * counterfactual_impact)
        else:
            final_reward = actual_reward + (0.15 * counterfactual_impact)

        assert isinstance(counterfactual_impact, float)
        self._last_counterfactual = counterfactual_impact
        info["counterfactual_impact"] = counterfactual_impact
        info["action_rollout_reward"] = (
            actual_cumulative_reward if evaluate_counterfactual else actual_reward
        )
        info["noop_rollout_reward"] = (
            noop_cumulative_reward if evaluate_counterfactual else actual_reward
        )
        info["debug"] = self._debug_snapshot()

        self.logs.append({
            "timestep": self.timestep,
            "action": deepcopy(normalized_action),
            "reward": final_reward,
            "pressure": self.system_pressure,
            "instability": self.instability_score,
            "counterfactual": counterfactual_impact,
            "chosen_over": {
                "noop": noop_cumulative_reward,
                "action": actual_cumulative_reward,
            },
            "effects_applied": deepcopy(self._due_effects_this_step),
        })
        if len(self.logs) > 500:
            self.logs.pop(0)

        return observation, final_reward, done, info

    def _rollout_cumulative_reward(
        self,
        simulated_env: "ASCDCEnvironment",
        initial_action: Dict[str, Any],
        horizon: int,
    ) -> float:
        # Compare intervention against intentional waiting over the same future horizon.
        total_reward = 0.0
        action = deepcopy(initial_action)

        for step_index in range(max(1, int(horizon))):
            _, reward, done, _ = simulated_env.step(
                action,
                evaluate_counterfactual=False,
            )
            discount = 0.9 ** step_index
            total_reward += float(reward) * discount
            if done:
                break
            if step_index == 0:
                action = {"type": "noop", "target": None}

        return total_reward

    def _execute_step(self, normalized_action: Dict[str, Any]):
        current_state = self._evaluation_state_snapshot()
        applied_action, action_status = self._validate_action(normalized_action)

        # Convert the current action into delayed effects instead of applying it immediately.
        if applied_action["type"] != "noop":
            self.noop_streak = 0
            self.steps_since_action = 0
            self._apply_action_constraints(applied_action)
            self._schedule_action_effects(applied_action)
        else:
            # Consecutive noops are tracked so restraint can be rewarded or punished later.
            self.noop_streak += 1
            self.steps_since_action += 1

        self._simulate_flow()
        self._update_metrics()
        current_latency = self._current_latency()
        self.pressure_delta = self.system_pressure - self.prev_pressure
        self.latency_delta = current_latency - self.prev_latency
        step_metrics = evaluate_step_metrics(
            current_state,
            applied_action,
            self._evaluation_state_snapshot(),
        )

        reward = self._compute_reward(applied_action, step_metrics) - action_status["penalty"]
        if (
            self.last_action_type is not None
            and self.last_action_type != applied_action["type"]
            and self.last_action_type != "noop"
            and applied_action["type"] != "noop"
        ):
            reward -= 0.2

        self.timestep += 1
        self._expire_action_locks()
        done = self.timestep >= self.max_timesteps

        observation = self._build_observation()
        observation.done = done
        info = {
            "latency": observation.latency,
            "latency_delta": self.latency_delta,
            "pressure": observation.system_pressure,
            "pressure_delta": self.pressure_delta,
            "remaining_budget": observation.remaining_budget,
            "system_pressure": observation.system_pressure,
            "instability_score": self.instability_score,
            "drift_score": self.drift_score,
            "smoothed_drift": self.smoothed_drift,
            "steps_since_action": self.steps_since_action,
            "noop_streak": self.noop_streak,
            "effects_applied": deepcopy(self._due_effects_this_step),
            "failure_flags": {
                "collapsed": self.system_pressure > 5.0,
                "budget_exhausted": action_status["reason"] == "budget_exhausted",
            },
            "queues": self.queues.copy(),
            "capacities": self.capacities.copy(),
            "retry_rate": self.retry_rate,
            "error_rate": self.error_rate,
            "pending_effects": deepcopy(self.pending_effects),
            "active_locks": deepcopy(self.active_locks),
            "stability": step_metrics["stability"],
            "necessity": step_metrics["necessity"],
            "action_rejected": action_status["rejected"],
            "rejection_reason": action_status["reason"],
            "requested_action": deepcopy(normalized_action),
            "applied_action": deepcopy(applied_action),
            "action_cost": action_status["cost"],
        }

        self.last_action_type = applied_action["type"]
        self.prev_pressure = self.system_pressure
        self.prev_latency = current_latency
        return observation, reward, done, info

    # ---------------- ACTIONS ---------------- #

    def _normalize_action(self, action: Any) -> Dict[str, Any]:
        if isinstance(action, dict):
            return {
                "type": str(action.get("type", "noop")).lower(),
                "target": action.get("target"),
                "magnitude": float(action.get("magnitude", 1.0)),
            }

        if hasattr(action, "type"):
            return {
                "type": str(getattr(action, "type", "noop")).lower(),
                "target": getattr(action, "target", None),
                "magnitude": float(getattr(action, "magnitude", 1.0)),
            }

        if hasattr(action, "__dict__"):
            action_dict = action.__dict__
            return {
                "type": str(action_dict.get("type", "noop")).lower(),
                "target": action_dict.get("target", None),
                "magnitude": float(action_dict.get("magnitude", 1.0)),
            }

        return {"type": "noop", "target": None, "magnitude": 1.0}

    def _validate_action(self, action: Dict[str, Any]) -> tuple[Dict[str, Any], Dict[str, Any]]:
        action_type = action["type"]
        target = action.get("target")
        cost = float(self.ACTION_COSTS.get(action_type, 0.0))
        status = {
            "rejected": False,
            "reason": None,
            "penalty": 0.0,
            "cost": cost,
        }

        if action_type == "noop":
            return action, status

        if target not in self.QUEUE_ORDER:
            status.update({
                "rejected": True,
                "reason": "invalid_target",
                "penalty": self.ACTION_REJECTION_PENALTY,
                "cost": 0.0,
            })
            return {"type": "noop", "target": None, "magnitude": 1.0}, status

        if self._is_target_locked(target):
            status.update({
                "rejected": True,
                "reason": "target_locked",
                "penalty": self.ACTION_REJECTION_PENALTY,
                "cost": 0.0,
            })
            return {"type": "noop", "target": None, "magnitude": 1.0}, status

        if self.remaining_budget < cost:
            status.update({
                "rejected": True,
                "reason": "budget_exhausted",
                "penalty": self.ACTION_REJECTION_PENALTY,
                "cost": 0.0,
            })
            return {"type": "noop", "target": None, "magnitude": 1.0}, status

        return action, status

    def _apply_action_constraints(self, action: Dict[str, Any]) -> None:
        action_type = action["type"]
        target = action.get("target")
        cost = float(self.ACTION_COSTS.get(action_type, 0.0))
        self.remaining_budget = max(0.0, self.remaining_budget - cost)

        lock_duration = self.ACTION_LOCK_DURATIONS.get(action_type)
        if target in self.QUEUE_ORDER and lock_duration is not None:
            self.active_locks[target] = self.timestep + lock_duration + 1

    def _expire_action_locks(self) -> None:
        self.active_locks = {
            target: unlock_timestep
            for target, unlock_timestep in self.active_locks.items()
            if self.timestep < int(unlock_timestep)
        }

    def _is_target_locked(self, target: Optional[str]) -> bool:
        if target not in self.QUEUE_ORDER:
            return False
        unlock_timestep = self.active_locks.get(target)
        if unlock_timestep is None:
            return False
        return self.timestep < int(unlock_timestep)

    def _schedule_action_effects(self, action: Dict[str, Any]) -> None:
        action_type = action["type"]
        target = action["target"]
        magnitude = max(float(action.get("magnitude", 1.0)), 0.0)

        if target not in self.QUEUE_ORDER:
            return

        effects: List[Dict[str, Any]] = []

        if action_type == "scale":
            effects.extend([
                {
                    "type": "scale",
                    "target": target,
                    "magnitude": 8.0 * magnitude,
                    "apply_at": self.timestep + self.SCALE_DELAY,
                },
                {
                    "type": "instability_penalty",
                    "target": target,
                    "magnitude": 0.08 * magnitude,
                    "apply_at": self.timestep + 5,
                },
            ])
        elif action_type == "restart":
            effects.extend([
                {
                    "type": "restart",
                    "target": target,
                    "magnitude": magnitude,
                    "apply_at": self.timestep + self.RESTART_DELAY,
                },
                {
                    "type": "retry_spike",
                    "target": target,
                    "magnitude": 0.15 * magnitude,
                    "apply_at": self.timestep + 3,
                },
                {
                    "type": "latency_spike",
                    "target": target,
                    "magnitude": 0.1 * magnitude,
                    "apply_at": self.timestep + 4,
                },
            ])
        elif action_type == "throttle":
            # Throttle unfolds over several steps to model a gradual control response.
            for step_offset, effect_magnitude in enumerate((0.26, 0.20, 0.15, 0.10, 0.06), start=self.THROTTLE_DELAY):
                effects.append({
                    "type": "throttle",
                    "target": target,
                    "magnitude": effect_magnitude * magnitude,
                    "apply_at": self.timestep + step_offset,
                })

        self.pending_effects.extend(effects)

    def _process_pending_effects(self) -> None:
        if not self.pending_effects:
            self._due_effects_this_step = []
            return

        due_effects = [
            effect for effect in self.pending_effects
            if int(effect.get("apply_at", -1)) == self.timestep
        ]
        self._due_effects_this_step = deepcopy(due_effects)
        self.pending_effects = [
            effect for effect in self.pending_effects
            if int(effect.get("apply_at", -1)) != self.timestep
        ]

        for effect in due_effects:
            self._apply_effect(effect)

    def _apply_effect(self, effect: Dict[str, Any]) -> None:
        effect_type = effect["type"]
        target = effect["target"]
        magnitude = max(float(effect.get("magnitude", 0.0)), 0.0)

        if target not in self.QUEUE_ORDER:
            return

        if effect_type == "restart":
            self.queues[target] = 0.0
        elif effect_type == "scale":
            self.capacities[target] += magnitude
        elif effect_type == "throttle":
            self._throttle_effects[target] = self._throttle_effects.get(target, 0.0) + magnitude
        elif effect_type == "retry_spike":
            self._retry_spike += magnitude
        elif effect_type == "latency_spike":
            self._latency_spikes[target] = self._latency_spikes.get(target, 0.0) + magnitude
        elif effect_type == "instability_penalty":
            self._instability_penalty += magnitude

    # ---------------- DYNAMICS ---------------- #

    def _simulate_flow(self) -> None:
        carry = 0.0
        scheduled_load = self.load_schedule.get(self.timestep, {})

        for queue in self.QUEUE_ORDER:
            noise = self.rng.uniform(0.85, 1.25)

            effective_load = float(scheduled_load.get(queue, self.base_load.get(queue, 1.0)))
            if queue in self._throttle_effects:
                effective_load *= 0.6
                self._throttle_effects[queue] *= 0.8
                if self._throttle_effects[queue] < 0.05:
                    del self._throttle_effects[queue]

            arrival = effective_load * noise

            if self.rng.random() < 0.12:
                arrival *= self.rng.uniform(1.5, 2.5)

            arrival += carry

            available = self.queues.get(queue, 0.0) + arrival
            capacity = max(self.capacities.get(queue, 1.0), 1.0)

            serviced = min(available, capacity)
            self.queues[queue] = max(0.0, available - serviced)
            carry = serviced

    # ---------------- METRICS ---------------- #

    def _update_metrics(self) -> None:
        utilization = sum(
            self.queues[queue] / max(self.capacities.get(queue, 1.0), 1.0)
            for queue in self.QUEUE_ORDER
        ) / len(self.QUEUE_ORDER)

        for queue in self.QUEUE_ORDER:
            capacity = max(self.capacities.get(queue, 1.0), 1.0)
            pressure = self.queues.get(queue, 0.0) / capacity
            latency_spike = self._latency_spikes.get(queue, 0.0)
            self.latencies[queue] = self.base_latencies.get(queue, 1.0) * (1 + pressure) + latency_spike

        base_retry = min(2.0, 0.35 * self.retry_rate + 0.65 * utilization)
        base_error = min(2.0, 0.35 * self.error_rate + 0.65 * utilization)
        base_pressure = utilization + base_retry + base_error

        if utilization > 0.6:
            self.drift_score += 0.02 * utilization

        if self.system_pressure < 0.5:
            self.drift_score *= 0.85
        if self.system_pressure < 0.3:
            self.drift_score *= 0.7

        self.smoothed_drift = 0.8 * self.smoothed_drift + 0.2 * self.drift_score

        # Sustained high pressure accumulates instability that compounds future degradation.
        if (self.prev_pressure - base_pressure) >= self.INSTABILITY_RESET_DELTA:
            self.instability_score *= 0.35
        elif base_pressure > self.INSTABILITY_PRESSURE_THRESHOLD:
            pressure_excess = base_pressure - self.INSTABILITY_PRESSURE_THRESHOLD
            self.instability_score += pressure_excess * self.INSTABILITY_GROWTH_RATE
        else:
            self.instability_score *= 0.82

        if base_pressure < 0.9:
            self.instability_score *= 0.8
        self.instability_score = min(3.0, max(0.0, self.instability_score))
        escalation = 0.0
        if self.instability_score > 0.0:
            escalation = min(3.0, math.exp(min(self.instability_score, 3.0) * 0.4) - 1.0)

        if self._retry_spike > 0.0:
            base_retry = min(2.0, base_retry + self._retry_spike)

        if self._instability_penalty > 0.0:
            base_retry = min(2.0, base_retry + 0.35 * self._instability_penalty)
            base_error = min(2.0, base_error + 0.25 * self._instability_penalty)

        if escalation > 0.0:
            base_retry = min(2.0, base_retry + 0.12 * escalation + 0.08 * self.instability_score)
            base_error = min(2.0, base_error + 0.18 * escalation + 0.1 * self.instability_score)

        self.retry_rate = min(2.0, max(0.0, base_retry))
        self.error_rate = min(2.0, max(0.0, base_error))
        self.instability_score = min(3.0, max(0.0, self.instability_score))
        self.retry_rate = min(2.0, max(0.0, self.retry_rate))
        self.error_rate = min(2.0, max(0.0, self.error_rate))
        self.system_pressure = utilization + 0.75 * self.retry_rate + 0.75 * self.error_rate
        self.system_pressure = max(0.0, self.system_pressure)
        assert 0.0 <= self.instability_score <= 3.0
        assert 0.0 <= self.retry_rate <= 2.0
        assert 0.0 <= self.error_rate <= 2.0
        self._latency_spikes.clear()
        self._retry_spike = 0.0
        self._instability_penalty = 0.0

    # ---------------- REWARD ---------------- #

    def _compute_reward(self, action: Dict[str, Any], step_metrics: Dict[str, Any]) -> float:
        latency_penalty = sum(self.latencies.values()) / len(self.latencies)
        queue_pressure_penalty = sum(
            self.queues[queue] / max(self.capacities.get(queue, 1.0), 1.0)
            for queue in self.QUEUE_ORDER
        ) / len(self.QUEUE_ORDER)
        stability_bonus = 3.6

        reward = (
            stability_bonus
            - 0.8 * latency_penalty
            - 1.1 * queue_pressure_penalty
            - 0.85 * self.retry_rate
            - 0.85 * self.error_rate
            - 0.1 * float(step_metrics["instability_score"])
            - 0.12 * self.drift_score
        )
        reward += 0.3 * (float(step_metrics["stability"]) - 0.5)

        if float(step_metrics["pressure_delta"]) < 0:
            reward += 0.5
        if float(step_metrics["pressure_delta"]) <= -0.5:
            reward += 1.0

        action_type = action["type"]
        if action_type == "restart":
            reward -= 0.06
        elif action_type == "scale":
            reward -= 0.02
        elif action_type == "throttle":
            reward -= 0.015

        if action_type != "noop":
            if bool(step_metrics["timing_window"]):
                reward += 0.8
            elif bool(step_metrics["premature_action"]):
                reward -= 0.35
            elif bool(step_metrics["late_action"]):
                reward -= 0.2

        if action_type == "noop":
            # Waiting is strategic: rewarded in calm states, punished when instability keeps building.
            stable_system = (
                not bool(step_metrics["necessity"])
                and
                queue_pressure_penalty < self.STABLE_NOOP_QUEUE_THRESHOLD
                and self.system_pressure < self.STABLE_NOOP_PRESSURE_THRESHOLD
                and float(step_metrics["instability_score"]) <= 0.05
            )
            if stable_system:
                reward += self.NOOP_STABLE_BONUS * min(self.noop_streak, 4)
            else:
                reward -= self.NOOP_UNSTABLE_PENALTY * max(1, self.noop_streak)

        if (
            self.steps_since_action > 3
            and (self.system_pressure > 0.8 or self.drift_score > 0.2)
        ):
            reward -= 0.03 * self.steps_since_action

        return reward

    # ---------------- STATE ---------------- #

    def state(self) -> Dict[str, Any]:
        """Return the current internal state."""
        return {
            "timestep": self.timestep,
            "remaining_budget": self.remaining_budget,
            "queues": deepcopy(self.queues),
            "capacities": deepcopy(self.capacities),
            "latencies": deepcopy(self.latencies),
            "base_load": deepcopy(self.base_load),
            "load_schedule": deepcopy(self.load_schedule),
            "retry_rate": self.retry_rate,
            "error_rate": self.error_rate,
            "pressure": self.system_pressure,
            "pressure_delta": self.pressure_delta,
            "latency": self._current_latency(),
            "latency_delta": self.latency_delta,
            "system_pressure": self.system_pressure,
            "instability_score": self.instability_score,
            "drift_score": self.drift_score,
            "smoothed_drift": self.smoothed_drift,
            "steps_since_action": self.steps_since_action,
            "noop_streak": self.noop_streak,
            "pending_effects": deepcopy(self.pending_effects),
            "active_locks": deepcopy(self.active_locks),
            "debug": self._debug_snapshot(),
            # Keep the existing UI contract intact.
            "pending_actions": self._serialize_pending_actions(),
            "throttle_effects": deepcopy(self._throttle_effects),
        }

    # ---------------- OUTPUT ---------------- #

    def _serialize_pending_actions(self) -> List[Dict[str, Any]]:
        return [
            {
                "type": effect["type"],
                "target": effect["target"],
                "magnitude": float(effect.get("magnitude", 0.0)),
                "applies_at": int(effect["apply_at"]),
            }
            for effect in sorted(
                self.pending_effects,
                key=lambda effect: (int(effect["apply_at"]), str(effect["type"]), str(effect["target"])),
            )
        ]

    def _build_observation(self) -> Observation:
        return Observation(
            queues=deepcopy(self.queues),
            capacities=deepcopy(self.capacities),
            latencies=deepcopy(self.latencies),
            latency=self._current_latency(),
            retry_rate=self.retry_rate,
            error_rate=self.error_rate,
            remaining_budget=self.remaining_budget,
            system_pressure=self.system_pressure,
            timestep=self.timestep,
            done=False,
            pending_actions=self._serialize_pending_actions(),
        )

    def _current_latency(self) -> float:
        if not self.latencies:
            return 0.0
        return sum(self.latencies.values()) / len(self.latencies)

    def _debug_snapshot(self) -> Dict[str, Any]:
        return {
            "instability_score": self.instability_score,
            "drift_score": self.drift_score,
            "smoothed_drift": self.smoothed_drift,
            "steps_since_action": self.steps_since_action,
            "noop_streak": self.noop_streak,
            "counterfactual_last": float(self._last_counterfactual or 0.0),
            "pending_effects_count": len(self.pending_effects),
        }

    def _evaluation_state_snapshot(self) -> Dict[str, float]:
        return {
            "system_pressure": float(self.system_pressure),
            "instability_score": float(self.instability_score),
        }

    def clone(self) -> "ASCDCEnvironment":
        return deepcopy(self)

    def _clone_for_rollout(self) -> "ASCDCEnvironment":
        clone = self.clone()
        clone.rng.setstate(self.rng.getstate())
        clone._cf_active = False
        return clone

    def __deepcopy__(self, memo: Dict[int, Any]) -> "ASCDCEnvironment":
        cls = self.__class__
        result = cls.__new__(cls)
        memo[id(self)] = result

        for key, value in self.__dict__.items():
            if key == "rng":
                cloned_rng = random.Random()
                cloned_rng.setstate(self.rng.getstate())
                setattr(result, key, cloned_rng)
            elif key == "_cf_active":
                setattr(result, key, False)
            else:
                setattr(result, key, deepcopy(value, memo))

        return result
