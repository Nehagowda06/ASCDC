from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, DefaultDict, Dict, List, Optional, Tuple
import random


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


class ASCDCEnvironment:
    QUEUE_ORDER = ("A", "B", "C")

    DEFAULT_CAPACITIES = {"A": 16.0, "B": 14.0, "C": 12.0}
    DEFAULT_LATENCIES = {"A": 1.2, "B": 1.6, "C": 2.1}
    DEFAULT_BASE_LOAD = {"A": 18.0, "B": 5.0, "C": 3.0}

    def __init__(self, seed: Optional[int] = 0, max_timesteps: int = 50):
        self.seed = seed
        self._rng = random.Random(seed)

        self.default_max_timesteps = max_timesteps
        self.max_timesteps = max_timesteps

        self.capacities = deepcopy(self.DEFAULT_CAPACITIES)
        self.base_latencies = deepcopy(self.DEFAULT_LATENCIES)
        self.base_load = deepcopy(self.DEFAULT_BASE_LOAD)

        self.reset(seed=seed)

    def reset(self, seed: Optional[int] = None, config: Optional[Dict[str, Any]] = None) -> Observation:
        reset_seed = seed
        if reset_seed is None and config:
            reset_seed = config.get("seed")
        if reset_seed is not None:
            self.seed = reset_seed
            self._rng = random.Random(reset_seed)

        # Always rebuild from a clean default state first so tasks do not leak into one another.
        self.queues = {q: 0.0 for q in self.QUEUE_ORDER}
        self.capacities = deepcopy(self.DEFAULT_CAPACITIES)
        self.base_load = deepcopy(self.DEFAULT_BASE_LOAD)
        self.max_timesteps = self.default_max_timesteps
        self.load_schedule = {}

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
        
        # Reset throttle effects
        if hasattr(self, '_throttle_effects'):
            self._throttle_effects.clear()

        self.retry_rate = 0.08
        self.error_rate = 0.02
        self.system_pressure = 0.0

        self.timestep = 0

        return self._build_observation()

    def step(self, action: Action):
        action = self._normalize_action(action)

        # Apply action safely
        if action["type"] != "noop":
            self._apply_action(action)

        # Simulate system
        self._simulate_flow()

        # Update metrics
        self._update_metrics()

        # Compute reward
        reward = self._compute_reward(action)

        self.timestep += 1
        done = self.timestep >= self.max_timesteps

        obs = self._build_observation()
        obs.done = done

        return obs, reward, done, {
            "latency": obs.latency,
            "remaining_budget": obs.remaining_budget,
            "system_pressure": obs.system_pressure,
            "failure_flags": {
                "collapsed": self.system_pressure > 5.0
            },
            "queues": self.queues.copy(),
            "capacities": self.capacities.copy(),
            "retry_rate": self.retry_rate,
            "error_rate": self.error_rate
        }

    # ---------------- ACTIONS ---------------- #

    def _normalize_action(self, action: Any) -> Dict[str, Any]:
        if isinstance(action, dict):
            return {
                "type": action.get("type", "noop"),
                "target": action.get("target"),
                "magnitude": float(action.get("magnitude", 1.0)),
            }
        
        # Handle dataclass or object with attributes
        if hasattr(action, 'type'):
            return {
                "type": getattr(action, 'type', 'noop'),
                "target": getattr(action, 'target', None),
                "magnitude": float(getattr(action, 'magnitude', 1.0)),
            }
        
        # Handle Action dataclass
        if hasattr(action, '__dict__'):
            action_dict = action.__dict__
            return {
                "type": action_dict.get("type", "noop"),
                "target": action_dict.get("target", None),
                "magnitude": float(action_dict.get("magnitude", 1.0)),
            }

        return {"type": "noop", "target": None, "magnitude": 1.0}

    def _apply_action(self, action: Dict[str, Any]):
        t = action["type"]
        target = action["target"]

        if target not in self.QUEUE_ORDER:
            return

        if t == "restart":
            self.queues[target] = 0.0

        elif t == "scale":
            self.capacities[target] += 5.0

        elif t == "throttle":
            # Temporary throttle effect that decays over time
            if not hasattr(self, '_throttle_effects'):
                self._throttle_effects = {}
            self._throttle_effects[target] = self._throttle_effects.get(target, 0) + 0.3

    # ---------------- DYNAMICS ---------------- #

    def _simulate_flow(self):
        carry = 0.0
        scheduled_load = self.load_schedule.get(self.timestep, {}) if hasattr(self, "load_schedule") else {}

        for q in self.QUEUE_ORDER:
            noise = self._rng.uniform(0.85, 1.25)

            # Apply throttle effects with decay
            effective_load = float(scheduled_load.get(q, self.base_load.get(q, 1.0)))
            if hasattr(self, '_throttle_effects') and q in self._throttle_effects:
                throttle_factor = max(0.7, 1.0 - self._throttle_effects[q])
                effective_load *= throttle_factor
                # Decay throttle effect
                self._throttle_effects[q] *= 0.8
                if self._throttle_effects[q] < 0.05:
                    del self._throttle_effects[q]

            arrival = effective_load * noise

            # occasional spike
            if self._rng.random() < 0.12:
                arrival *= self._rng.uniform(1.5, 2.5)

            arrival += carry

            available = self.queues.get(q, 0.0) + arrival
            capacity = max(self.capacities.get(q, 1.0), 1.0)

            serviced = min(available, capacity)
            self.queues[q] = max(0.0, available - serviced)

            carry = serviced

    # ---------------- METRICS ---------------- #

    def _update_metrics(self):
        total_capacity = sum(self.capacities.values())
        if total_capacity <= 0:
            total_capacity = 1.0  # Prevent division by zero

        utilization = sum(
            self.queues[q] / max(self.capacities.get(q, 1.0), 1.0)
            for q in self.QUEUE_ORDER
        ) / len(self.QUEUE_ORDER)

        for q in self.QUEUE_ORDER:
            capacity = max(self.capacities.get(q, 1.0), 1.0)
            pressure = self.queues.get(q, 0.0) / capacity
            self.latencies[q] = self.base_latencies.get(q, 1.0) * (1 + pressure)

        self.retry_rate = min(2.0, 0.5 * self.retry_rate + 0.5 * utilization)
        self.error_rate = min(2.0, 0.5 * self.error_rate + 0.5 * utilization)

        self.system_pressure = utilization + self.retry_rate + self.error_rate

    # ---------------- REWARD ---------------- #

    def _compute_reward(self, action):
        latency_penalty = sum(self.latencies.values()) / len(self.latencies)
        queue_pressure_penalty = sum(
            self.queues[q] / max(self.capacities.get(q, 1.0), 1.0)
            for q in self.QUEUE_ORDER
        ) / len(self.QUEUE_ORDER)
        stability_bonus = 3.2

        reward = (
            stability_bonus
            - 0.8 * latency_penalty
            - 1.4 * queue_pressure_penalty
            - self.retry_rate
            - self.error_rate
        )

        action_type = action["type"]
        if action_type == "restart":
            reward -= 0.1
        elif action_type == "scale":
            reward -= 0.04
        elif action_type == "throttle":
            reward -= 0.03

        # Discourage waiting only when the system is already under meaningful strain.
        if action_type == "noop":
            if queue_pressure_penalty >= 0.75 or self.system_pressure >= 1.0:
                reward -= 0.08

        return reward

    def state(self) -> Dict[str, Any]:
        """Return current internal state for debugging/inspection."""
        return {
            "timestep": self.timestep,
            "remaining_budget": self.remaining_budget,
            "queues": deepcopy(self.queues),
            "capacities": deepcopy(self.capacities),
            "latencies": deepcopy(self.latencies),
            "base_load": deepcopy(self.base_load),
            "load_schedule": deepcopy(getattr(self, "load_schedule", {})),
            "retry_rate": self.retry_rate,
            "error_rate": self.error_rate,
            "system_pressure": self.system_pressure,
            "throttle_effects": getattr(self, '_throttle_effects', {}),
        }

    # ---------------- OUTPUT ---------------- #

    def _build_observation(self) -> Observation:
        return Observation(
            queues=deepcopy(self.queues),
            capacities=deepcopy(self.capacities),
            latencies=deepcopy(self.latencies),
            latency=sum(self.latencies.values()) / len(self.latencies),
            retry_rate=self.retry_rate,
            error_rate=self.error_rate,
            remaining_budget=self.remaining_budget,
            system_pressure=self.system_pressure,
            timestep=self.timestep,
            done=False,
        )
