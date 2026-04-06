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

        self.max_timesteps = max_timesteps

        self.capacities = deepcopy(self.DEFAULT_CAPACITIES)
        self.base_latencies = deepcopy(self.DEFAULT_LATENCIES)
        self.base_load = deepcopy(self.DEFAULT_BASE_LOAD)

        self.reset(seed=seed)

    def reset(self, seed: Optional[int] = None) -> Observation:
        if seed is not None:
            self._rng = random.Random(seed)

        self.queues = {q: 0.0 for q in self.QUEUE_ORDER}
        self.latencies = deepcopy(self.base_latencies)

        self.retry_rate = 0.08
        self.error_rate = 0.02
        self.remaining_budget = 100.0
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

        return obs, reward, done, {}

    # ---------------- ACTIONS ---------------- #

    def _normalize_action(self, action: Any) -> Dict[str, Any]:
        if isinstance(action, dict):
            return {
                "type": action.get("type", "noop"),
                "target": action.get("target"),
                "magnitude": float(action.get("magnitude", 1.0)),
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
            self.base_load[target] *= 0.7

    # ---------------- DYNAMICS ---------------- #

    def _simulate_flow(self):
        carry = 0.0

        for q in self.QUEUE_ORDER:
            noise = self._rng.uniform(0.85, 1.25)

            arrival = self.base_load[q] * noise

            # occasional spike
            if self._rng.random() < 0.12:
                arrival *= self._rng.uniform(1.5, 2.5)

            arrival += carry

            available = self.queues[q] + arrival
            capacity = max(self.capacities[q], 1.0)

            serviced = min(available, capacity)
            self.queues[q] = max(0.0, available - serviced)

            carry = serviced

    # ---------------- METRICS ---------------- #

    def _update_metrics(self):
        total_capacity = sum(self.capacities.values())

        utilization = sum(
            self.queues[q] / max(self.capacities[q], 1.0)
            for q in self.QUEUE_ORDER
        ) / len(self.QUEUE_ORDER)

        for q in self.QUEUE_ORDER:
            pressure = self.queues[q] / max(self.capacities[q], 1.0)
            self.latencies[q] = self.base_latencies[q] * (1 + pressure)

        self.retry_rate = min(2.0, 0.5 * self.retry_rate + 0.5 * utilization)
        self.error_rate = min(2.0, 0.5 * self.error_rate + 0.5 * utilization)

        self.system_pressure = utilization + self.retry_rate + self.error_rate

    # ---------------- REWARD ---------------- #

    def _compute_reward(self, action):
        latency_penalty = sum(self.latencies.values()) / len(self.latencies)

        reward = -latency_penalty - self.retry_rate - self.error_rate

        # discourage useless noop
        if action["type"] == "noop":
            reward -= 0.05

        return reward

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
