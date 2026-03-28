from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from dataclasses import asdict, dataclass, is_dataclass
import inspect
from typing import Any, DefaultDict, Dict, List, Mapping, Optional, Tuple

try:
    from models import Action as ImportedAction
    from models import Observation as ImportedObservation
    from models import State as ImportedState
except (ImportError, AttributeError):
    ImportedAction = None
    ImportedObservation = None
    ImportedState = None


if ImportedAction is None:
    @dataclass(frozen=True)
    class Action:
        type: str = "noop"
        target: Optional[str] = None
        cost: Optional[float] = None
        delay: Optional[int] = None
        lock_duration: Optional[int] = None
        magnitude: float = 1.0
else:
    Action = ImportedAction


if ImportedObservation is None:
    @dataclass(frozen=True)
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
else:
    Observation = ImportedObservation


if ImportedState is None:
    @dataclass(frozen=True)
    class State:
        queues: Dict[str, float]
        capacities: Dict[str, float]
        latencies: Dict[str, float]
        latency: float
        retry_rate: float
        error_rate: float
        remaining_budget: float
        timestep: int
        true_load: Dict[str, float]
        retry_amplification_factor: float
        delayed_effect_queue: Dict[int, List[Dict[str, Any]]]
        failure_flags: Dict[str, bool]
        history: List[Dict[str, Any]]
        seed: Optional[int]
else:
    State = ImportedState


class ASCDCEnvironment:
    QUEUE_ORDER: Tuple[str, str, str] = ("A", "B", "C")
    UPSTREAM: Dict[str, Optional[str]] = {"A": None, "B": "A", "C": "B"}
    DOWNSTREAM: Dict[str, Optional[str]] = {"A": "B", "B": "C", "C": None}

    DEFAULT_CAPACITIES: Dict[str, float] = {"A": 16.0, "B": 14.0, "C": 12.0}
    DEFAULT_LATENCIES: Dict[str, float] = {"A": 1.2, "B": 1.6, "C": 2.1}
    DEFAULT_BASE_LOAD: Dict[str, float] = {"A": 12.0, "B": 1.5, "C": 1.0}
    DEFAULT_ACTION_SPECS: Dict[str, Dict[str, float]] = {
        "restart": {
            "cost": 16.0,
            "delay": 1.0,
            "lock_duration": 2.0,
            "queue_clear_ratio": 1.0,
            "upstream_retry_increase": 0.12,
        },
        "scale": {
            "cost": 10.0,
            "delay": 2.0,
            "lock_duration": 2.0,
            "capacity_delta": 6.0,
            "downstream_push_ratio": 0.5,
        },
        "throttle": {
            "cost": 6.0,
            "delay": 0.0,
            "lock_duration": 1.0,
            "load_reduction": 0.18,
            "min_factor": 0.35,
        },
        "noop": {
            "cost": 0.0,
            "delay": 0.0,
            "lock_duration": 0.0,
        },
    }

    def __init__(
        self,
        *,
        seed: Optional[int] = 0,
        max_timesteps: int = 50,
        initial_budget: float = 100.0,
        capacities: Optional[Mapping[str, float]] = None,
        latencies: Optional[Mapping[str, float]] = None,
        base_load: Optional[Mapping[str, float]] = None,
        retry_rate: float = 0.08,
        error_rate: float = 0.02,
        action_specs: Optional[Mapping[str, Mapping[str, float]]] = None,
        collapse_pressure: float = 3.0,
        collapse_error_rate: float = 1.0,
        collapse_queue_ratio: float = 3.5,
    ) -> None:
        self.seed = seed
        self.max_timesteps = int(max_timesteps)
        self.initial_budget = float(initial_budget)
        self.initial_capacities = self._merge_metric(self.DEFAULT_CAPACITIES, capacities)
        self.initial_latency_bases = self._merge_metric(self.DEFAULT_LATENCIES, latencies)
        self.initial_base_load = self._merge_metric(self.DEFAULT_BASE_LOAD, base_load)
        self.initial_retry_rate = float(retry_rate)
        self.initial_error_rate = float(error_rate)
        self.action_specs = self._build_action_specs(action_specs)
        self.collapse_pressure = float(collapse_pressure)
        self.collapse_error_rate = float(collapse_error_rate)
        self.collapse_queue_ratio = float(collapse_queue_ratio)
        self.collapse_latency = max(self.initial_latency_bases.values()) * 4.0

        self.queues: Dict[str, float] = {}
        self.capacities: Dict[str, float] = {}
        self.base_latencies: Dict[str, float] = {}
        self.latencies: Dict[str, float] = {}
        self.base_load: Dict[str, float] = {}
        self.true_load: Dict[str, float] = {}
        self.retry_rate = 0.0
        self.error_rate = 0.0
        self.remaining_budget = 0.0
        self.system_pressure = 0.0
        self.retry_amplification_factor = 1.0
        self.pending_downstream_push: Dict[str, float] = {}
        self.throttle_factors: Dict[str, float] = {}
        self.dropped_requests: Dict[str, float] = {}
        self.locked_actions: Dict[Tuple[str, Optional[str]], int] = {}
        self.delayed_effect_queue: DefaultDict[int, List[Dict[str, Any]]] = defaultdict(list)
        self.failure_flags: Dict[str, bool] = {}
        self.history: List[Dict[str, Any]] = []
        self.timestep = 0
        self.current_step_dropped = 0.0

        self.reset(seed=seed)

    def reset(self, seed: Optional[int] = None, config: Optional[dict] = None) -> Observation:
        if seed is not None:
            self.seed = seed

        self.queues = {queue: 0.0 for queue in self.QUEUE_ORDER}
        self.capacities = deepcopy(self.initial_capacities)
        self.base_latencies = deepcopy(self.initial_latency_bases)
        self.latencies = deepcopy(self.initial_latency_bases)
        self.base_load = deepcopy(self.initial_base_load)
        self.true_load = deepcopy(self.initial_base_load)
        self.retry_rate = self.initial_retry_rate
        self.error_rate = self.initial_error_rate
        self.remaining_budget = self.initial_budget
        self.system_pressure = 0.0
        self.retry_amplification_factor = 1.0
        self.pending_downstream_push = {queue: 0.0 for queue in self.QUEUE_ORDER}
        self.throttle_factors = {queue: 1.0 for queue in self.QUEUE_ORDER}
        self.dropped_requests = {queue: 0.0 for queue in self.QUEUE_ORDER}
        self.locked_actions = {}
        self.delayed_effect_queue = defaultdict(list)
        self.failure_flags = {
            "budget_exhausted": self.remaining_budget <= 0.0,
            "queue_overflow": False,
            "latency_spike": False,
            "error_spike": False,
            "collapsed": False,
        }
        self.history = []
        self.timestep = 0
        self.current_step_dropped = 0.0

        if config:
            if "base_load" in config:
                self.base_load = dict(config["base_load"])
                self.true_load = dict(config["base_load"])

            if "capacities" in config:
                self.capacities = dict(config["capacities"])

            if "initial_queues" in config:
                for k in self.queues:
                    self.queues[k] = config["initial_queues"].get(k, 0.0)

            if "initial_budget" in config:
                self.remaining_budget = float(config["initial_budget"])

            if "max_timesteps" in config:
                self.max_timesteps = int(config["max_timesteps"])

            # store load schedule
            self.load_schedule = config.get("load_schedule", {})
        else:
            self.load_schedule = {}

        return self._build_observation()

    def step(self, action: Any) -> Tuple[Observation, float, bool, Dict[str, Any]]:
        if hasattr(self, "load_schedule") and self.timestep in self.load_schedule:
            overrides = self.load_schedule[self.timestep]
            for k, v in overrides.items():
                if k in self.base_load:
                    self.base_load[k] = float(v)

        self._purge_expired_locks(self.timestep)
        decision_timestep = self.timestep
        previous_queue_total = sum(self.queues.values())

        requested_action = self._normalize_action(action)

        # 1. validate action
        applied_action, validation = self._validate_action(requested_action)

        # 2. apply cost
        action_cost = float(applied_action["cost"])
        self.remaining_budget = max(0.0, self.remaining_budget - action_cost)

        # 3. apply lock
        if applied_action["type"] != "noop" and applied_action["lock_duration"] > 0 and applied_action["target"]:
            expiry_step = decision_timestep + int(applied_action["lock_duration"]) + 1
            self.locked_actions[(applied_action["type"], applied_action["target"])] = expiry_step

        # 4. enqueue delayed effect
        scheduled_timestep = decision_timestep + int(applied_action["delay"])
        self.delayed_effect_queue[scheduled_timestep].append(deepcopy(applied_action))

        # 5. process delayed effects
        self.current_step_dropped = 0.0
        due_effects = self.delayed_effect_queue.pop(decision_timestep, [])
        applied_effects = [self._apply_action_effect(effect) for effect in due_effects]

        # 6. propagate system dynamics
        prev_pressure = self.system_pressure
        dynamics = self._propagate_system_dynamics()

        # 7. update metrics
        queue_total = sum(self.queues.values())
        queue_growth = queue_total - previous_queue_total
        self._update_metrics(queue_growth)
        pressure_delta = prev_pressure - self.system_pressure

        # 8. compute reward
        reward = self._compute_reward(queue_growth, action_cost)
        reward += pressure_delta

        # 9. increment timestep
        self.timestep += 1
        self._purge_expired_locks(self.timestep)

        # 10. return observation, reward, done, info
        done = self._check_done()
        observation = self._build_observation()
        info = {
            "requested_action": deepcopy(requested_action),
            "applied_action": deepcopy(applied_action),
            "action_valid": validation["valid"],
            "invalid_reason": validation["reason"],
            "scheduled_timestep": scheduled_timestep,
            "applied_effects": applied_effects,
            "pressure_delta": pressure_delta,
            "stability_score": max(0.0, 1.0 - self.system_pressure),
            "remaining_budget": self.remaining_budget,
            "queue_growth": queue_growth,
            "latency": self._aggregate_latency(),
            "system_pressure": self.system_pressure,
            "retry_rate": self.retry_rate,
            "error_rate": self.error_rate,
            "locked_actions": self._active_locks_snapshot(),
            "failure_flags": deepcopy(self.failure_flags),
            "dynamics": dynamics,
        }

        self.history.append(
            {
                "decision_timestep": decision_timestep,
                "requested_action": deepcopy(requested_action),
                "applied_action": deepcopy(applied_action),
                "action_valid": validation["valid"],
                "invalid_reason": validation["reason"],
                "scheduled_timestep": scheduled_timestep,
                "applied_effects": deepcopy(applied_effects),
                "reward": reward,
                "done": done,
                "observation": self._observation_payload(),
                "info": deepcopy(info),
            }
        )

        return observation, reward, done, info

    def state(self) -> State:
        payload = self._state_payload()
        return self._build_model(State, payload)

    def _merge_metric(
        self,
        defaults: Mapping[str, float],
        overrides: Optional[Mapping[str, float]],
    ) -> Dict[str, float]:
        merged = {queue: float(defaults[queue]) for queue in self.QUEUE_ORDER}
        if overrides:
            for queue, value in overrides.items():
                if queue in merged:
                    merged[queue] = float(value)
        return merged

    def _build_action_specs(
        self,
        overrides: Optional[Mapping[str, Mapping[str, float]]],
    ) -> Dict[str, Dict[str, float]]:
        specs = {
            name: {key: float(value) for key, value in values.items()}
            for name, values in self.DEFAULT_ACTION_SPECS.items()
        }
        if overrides:
            for name, values in overrides.items():
                normalized_name = str(name).lower()
                specs.setdefault(normalized_name, {})
                for key, value in values.items():
                    specs[normalized_name][key] = float(value)
        return specs

    def _normalize_action(self, action: Any) -> Dict[str, Any]:
        if action is None:
            raw_action = {"type": "noop"}
        elif isinstance(action, str):
            raw_action = {"type": action}
        else:
            raw_action = self._object_to_mapping(action)

        action_type = str(
            self._lookup_value(raw_action, "type", "action_type", "kind", "name", default="noop")
        ).lower()
        target = self._lookup_value(
            raw_action,
            "target",
            "queue",
            "service",
            "component",
            "node",
            default=None,
        )
        if isinstance(target, str):
            target = target.upper()

        spec = self.action_specs.get(action_type, self.action_specs["noop"])
        magnitude = float(self._lookup_value(raw_action, "magnitude", "amount", "size", default=1.0))
        cost = float(self._lookup_value(raw_action, "cost", "action_cost", default=spec.get("cost", 0.0)))
        delay = int(self._lookup_value(raw_action, "delay", "effect_delay", default=spec.get("delay", 0.0)))
        lock_duration = int(
            self._lookup_value(
                raw_action,
                "lock_duration",
                "cooldown",
                "lock",
                default=spec.get("lock_duration", 0.0),
            )
        )

        normalized = {
            "type": action_type,
            "target": target,
            "cost": max(0.0, cost),
            "delay": max(0, delay),
            "lock_duration": max(0, lock_duration),
            "magnitude": max(0.0, magnitude),
        }

        for extra_key, extra_value in spec.items():
            normalized.setdefault(extra_key, extra_value)

        for key, value in raw_action.items():
            normalized.setdefault(key, value)

        return normalized

    def _validate_action(self, action: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        action_type = action["type"]
        target = action["target"]

        if action_type not in self.action_specs:
            return self._noop_action(), {"valid": False, "reason": "unsupported_action"}

        if action_type != "noop" and target not in self.QUEUE_ORDER:
            return self._noop_action(), {"valid": False, "reason": "unknown_target"}

        if action["cost"] > self.remaining_budget:
            return self._noop_action(), {"valid": False, "reason": "budget_exceeded"}

        if action_type != "noop" and self._is_locked(action_type, target):
            return self._noop_action(), {"valid": False, "reason": "action_locked"}

        return deepcopy(action), {"valid": True, "reason": None}

    def _noop_action(self) -> Dict[str, Any]:
        noop_spec = self.action_specs["noop"]
        return {
            "type": "noop",
            "target": None,
            "cost": float(noop_spec.get("cost", 0.0)),
            "delay": int(noop_spec.get("delay", 0.0)),
            "lock_duration": int(noop_spec.get("lock_duration", 0.0)),
            "magnitude": 1.0,
        }

    def _is_locked(self, action_type: str, target: Optional[str]) -> bool:
        expiry = self.locked_actions.get((action_type, target))
        return expiry is not None and expiry > self.timestep

    def _purge_expired_locks(self, current_timestep: int) -> None:
        expired = [
            key
            for key, expiry in self.locked_actions.items()
            if expiry <= current_timestep
        ]
        for key in expired:
            del self.locked_actions[key]

    def _apply_action_effect(self, action: Dict[str, Any]) -> Dict[str, Any]:
        action_type = action["type"]
        target = action["target"]
        magnitude = float(action.get("magnitude", 1.0))

        if action_type == "restart" and target in self.QUEUE_ORDER:
            cleared = self.queues[target] * float(action.get("queue_clear_ratio", 1.0))
            self.queues[target] = max(0.0, self.queues[target] - cleared)
            upstream = self.UPSTREAM[target]
            retry_increase = float(action.get("upstream_retry_increase", 0.12)) * magnitude
            if upstream is not None:
                self.retry_amplification_factor += retry_increase
            else:
                self.retry_amplification_factor += retry_increase * 0.5

            return {
                "type": action_type,
                "target": target,
                "cleared_queue": cleared,
                "retry_amplification_factor": self.retry_amplification_factor,
            }

        if action_type == "scale" and target in self.QUEUE_ORDER:
            capacity_delta = float(action.get("capacity_delta", 6.0)) * magnitude
            self.capacities[target] += capacity_delta
            downstream = self.DOWNSTREAM[target]
            pushed = 0.0
            if downstream is not None:
                pushed = min(
                    self.queues[target],
                    capacity_delta * float(action.get("downstream_push_ratio", 0.5)),
                )
                self.queues[target] -= pushed
                self.pending_downstream_push[downstream] += pushed

            return {
                "type": action_type,
                "target": target,
                "capacity_delta": capacity_delta,
                "downstream_pushed": pushed,
            }

        if action_type == "throttle" and target in self.QUEUE_ORDER:
            reduction = float(action.get("load_reduction", 0.18)) * magnitude
            previous_factor = self.throttle_factors[target]
            min_factor = float(action.get("min_factor", 0.35))
            updated_factor = max(min_factor, previous_factor - reduction)
            self.throttle_factors[target] = updated_factor

            dropped = self.base_load[target] * (previous_factor - updated_factor)
            self.dropped_requests[target] += max(0.0, dropped)
            self.current_step_dropped += max(0.0, dropped)

            return {
                "type": action_type,
                "target": target,
                "throttle_factor": updated_factor,
                "dropped_requests": max(0.0, dropped),
            }

        return {
            "type": "noop",
            "target": None,
            "applied": False,
        }

    def _propagate_system_dynamics(self) -> Dict[str, Any]:
        arrivals: Dict[str, float] = {}
        serviced: Dict[str, float] = {}
        raw_load: Dict[str, float] = {}
        carry = 0.0

        for queue in self.QUEUE_ORDER:
            raw_arrival = self.base_load[queue] + self.pending_downstream_push[queue]
            if queue == "A":
                raw_arrival *= self.retry_amplification_factor
            else:
                raw_arrival += carry

            raw_load[queue] = raw_arrival
            throttled_arrival = raw_arrival * self.throttle_factors[queue]
            dropped = max(0.0, raw_arrival - throttled_arrival)
            self.dropped_requests[queue] += dropped
            self.current_step_dropped += dropped

            available = self.queues[queue] + throttled_arrival
            capacity = max(self.capacities[queue], 1.0)
            serviced_amount = min(available, capacity)
            self.queues[queue] = max(0.0, available - serviced_amount)
            carry = serviced_amount

            arrivals[queue] = throttled_arrival
            serviced[queue] = serviced_amount

        self.true_load = raw_load
        self.pending_downstream_push = {queue: 0.0 for queue in self.QUEUE_ORDER}

        average_utilization = sum(
            self.queues[queue] / max(self.capacities[queue], 1.0)
            for queue in self.QUEUE_ORDER
        ) / len(self.QUEUE_ORDER)

        for queue in self.QUEUE_ORDER:
            capacity = max(self.capacities[queue], 1.0)
            queue_pressure = self.queues[queue] / capacity
            self.latencies[queue] = self.base_latencies[queue] * (
                1.0 + queue_pressure + 0.35 * average_utilization
            )

        total_incoming = max(sum(raw_load.values()), 1.0)
        drop_ratio = self.current_step_dropped / total_incoming
        target_retry = (
            self.initial_retry_rate
            + 0.18 * average_utilization
            + 0.22 * max(0.0, self.retry_amplification_factor - 1.0)
            + 0.12 * drop_ratio
        )
        self.retry_rate = self._clamp((0.5 * self.retry_rate) + (0.5 * target_retry), 0.0, 2.5)
        self.retry_amplification_factor = 1.0 + (self.retry_amplification_factor - 1.0) * 0.7

        for queue in self.QUEUE_ORDER:
            self.throttle_factors[queue] = min(1.0, self.throttle_factors[queue] + 0.03)

        return {
            "arrivals": arrivals,
            "serviced": serviced,
            "true_load": deepcopy(raw_load),
        }

    def _update_metrics(self, queue_growth: float) -> None:
        total_capacity = max(sum(self.capacities.values()), 1.0)
        overflow = sum(
            max(0.0, self.queues[queue] - self.capacities[queue])
            for queue in self.QUEUE_ORDER
        )
        utilization = sum(
            self.queues[queue] / max(self.capacities[queue], 1.0)
            for queue in self.QUEUE_ORDER
        ) / len(self.QUEUE_ORDER)
        drop_ratio = self.current_step_dropped / max(sum(self.true_load.values()), 1.0)

        target_error = (
            self.initial_error_rate
            + 0.16 * utilization
            + 0.22 * drop_ratio
            + 0.18 * self.retry_rate
            + 0.12 * (overflow / total_capacity)
        )
        self.error_rate = self._clamp((0.4 * self.error_rate) + (0.6 * target_error), 0.0, 2.0)

        self.system_pressure = (
            utilization
            + 0.7 * self.retry_rate
            + 0.6 * self.error_rate
            + max(0.0, queue_growth) / total_capacity
        )

        self.failure_flags = {
            "budget_exhausted": self.remaining_budget <= 0.0,
            "queue_overflow": any(
                self.queues[queue] > (self.capacities[queue] * self.collapse_queue_ratio)
                for queue in self.QUEUE_ORDER
            ),
            "latency_spike": self._aggregate_latency() >= self.collapse_latency,
            "error_spike": self.error_rate >= self.collapse_error_rate,
            "collapsed": False,
        }
        self.failure_flags["collapsed"] = any(
            (
                self.failure_flags["queue_overflow"],
                self.failure_flags["latency_spike"],
                self.failure_flags["error_spike"],
                self.system_pressure >= self.collapse_pressure,
            )
        )

    def _compute_reward(self, queue_growth: float, action_cost: float) -> float:
        latency_penalty = self._aggregate_latency()
        retry_penalty = self.retry_rate
        growth_penalty = max(0.0, queue_growth)

        # Encourage stability
        stability_bonus = max(0.0, 1.0 - self.system_pressure)

        # Penalize unnecessary actions
        overreaction_penalty = 0.0
        if action_cost > 0 and self.system_pressure < 0.8:
            overreaction_penalty = action_cost * 0.5

        # Early intervention bonus
        early_bonus = 0.0
        if self.system_pressure > 1.2 and action_cost > 0:
            early_bonus = 1.0

        return (
            - latency_penalty
            - retry_penalty
            - growth_penalty
            - action_cost
            - overreaction_penalty
            + stability_bonus
            + early_bonus
        )

    def _check_done(self) -> bool:
        return (
            self.timestep >= self.max_timesteps
            or self.failure_flags["collapsed"]
            or self.failure_flags["budget_exhausted"]
        )

    def _aggregate_latency(self) -> float:
        return sum(self.latencies.values()) / len(self.latencies)

    def _observation_payload(self) -> Dict[str, Any]:
        payload = {
            "queues": deepcopy(self.queues),
            "queue_values": [self.queues[queue] for queue in self.QUEUE_ORDER],
            "capacities": deepcopy(self.capacities),
            "capacity_values": [self.capacities[queue] for queue in self.QUEUE_ORDER],
            "latencies": deepcopy(self.latencies),
            "latency_values": [self.latencies[queue] for queue in self.QUEUE_ORDER],
            "latency": self._aggregate_latency(),
            "retry_rate": self.retry_rate,
            "error_rate": self.error_rate,
            "remaining_budget": self.remaining_budget,
            "budget": self.remaining_budget,
            "system_pressure": self.system_pressure,
            "pending_actions": [
                {
                    "type": action["type"],
                    "target": action["target"],
                    "applies_at": timestep,
                }
                for timestep, actions in self.delayed_effect_queue.items()
                for action in actions
            ],
            "timestep": self.timestep,
        }
        for queue in self.QUEUE_ORDER:
            lower = queue.lower()
            payload[f"queue_{lower}"] = self.queues[queue]
            payload[f"capacity_{lower}"] = self.capacities[queue]
            payload[f"latency_{lower}"] = self.latencies[queue]
        return payload

    def _state_payload(self) -> Dict[str, Any]:
        payload = self._observation_payload()
        payload.update(
            {
                "true_load": deepcopy(self.true_load),
                "retry_amplification_factor": self.retry_amplification_factor,
                "delayed_effect_queue": {
                    timestep: deepcopy(actions)
                    for timestep, actions in self.delayed_effect_queue.items()
                },
                "failure_flags": deepcopy(self.failure_flags),
                "history": deepcopy(self.history),
                "seed": self.seed,
                "locked_actions": self._active_locks_snapshot(),
                "throttle_factors": deepcopy(self.throttle_factors),
                "dropped_requests": deepcopy(self.dropped_requests),
            }
        )
        return payload

    def _build_observation(self) -> Observation:
        return self._build_model(Observation, self._observation_payload())

    def _build_model(self, model_cls: Any, payload: Dict[str, Any]) -> Any:
        copied_payload = deepcopy(payload)
        if model_cls is None:
            return copied_payload

        try:
            return model_cls(**copied_payload)
        except TypeError:
            pass

        try:
            signature = inspect.signature(model_cls)
        except (TypeError, ValueError):
            signature = None

        if signature is not None:
            kwargs = {}
            for name, parameter in signature.parameters.items():
                if name == "self":
                    continue
                if name in copied_payload:
                    kwargs[name] = deepcopy(copied_payload[name])
                elif parameter.default is inspect._empty:
                    break
            else:
                try:
                    return model_cls(**kwargs)
                except TypeError:
                    pass

        try:
            instance = model_cls()
        except Exception:
            return copied_payload

        for key, value in copied_payload.items():
            try:
                setattr(instance, key, deepcopy(value))
            except Exception:
                continue
        return instance

    def _object_to_mapping(self, value: Any) -> Dict[str, Any]:
        if value is None:
            return {}
        if isinstance(value, Mapping):
            return dict(value)
        if hasattr(value, "model_dump") and callable(value.model_dump):
            return dict(value.model_dump())
        if hasattr(value, "dict") and callable(value.dict):
            return dict(value.dict())
        if hasattr(value, "_asdict") and callable(value._asdict):
            return dict(value._asdict())
        if is_dataclass(value) and not isinstance(value, type):
            return asdict(value)
        if hasattr(value, "__dict__"):
            return {
                key: item
                for key, item in vars(value).items()
                if not key.startswith("_")
            }
        return {}

    def _lookup_value(self, payload: Mapping[str, Any], *aliases: str, default: Any = None) -> Any:
        normalized = {str(key).lower(): value for key, value in payload.items()}
        for alias in aliases:
            if alias.lower() in normalized:
                return normalized[alias.lower()]
        return default

    def _active_locks_snapshot(self) -> Dict[str, int]:
        snapshot: Dict[str, int] = {}
        for (action_type, target), expiry in self.locked_actions.items():
            label = f"{action_type}:{target}" if target is not None else action_type
            snapshot[label] = max(0, expiry - self.timestep)
        return snapshot

    @staticmethod
    def _clamp(value: float, minimum: float, maximum: float) -> float:
        return max(minimum, min(value, maximum))


__all__ = ["ASCDCEnvironment"]
