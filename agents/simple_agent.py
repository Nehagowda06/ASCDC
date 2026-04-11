"""Agent implementations for ASCDC."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable, Dict, List, Optional
import logging
import random

from core.agents.smart_agent import SmartAgent
<<<<<<< HEAD
from agents.cf_planner import CounterfactualPlannerAgent
=======
>>>>>>> 3f8b51ce07d34fbefba8a351d57cc42f33924908

logger = logging.getLogger(__name__)

class SimpleAgent:
    """A simple, reliable agent that makes logical decisions."""
    
    def __init__(self, strategy: str = "adaptive"):
        self.strategy = strategy
        self.name = f"Simple-{strategy}"
        
    def act(self, observation: Any) -> Dict[str, Any]:
        """Make a decision based on observation."""
        try:
            snapshot = self._normalize_observation(observation)
            queues = snapshot["queues"]

            if not queues:
                return {"type": "noop", "target": None}
            
            # Simple logic based on strategy
            if self.strategy == "adaptive":
                action = self._adaptive_strategy(snapshot)
            elif self.strategy == "conservative":
                action = self._conservative_strategy(snapshot)
            elif self.strategy == "aggressive":
                action = self._aggressive_strategy(snapshot)
            else:
                action = {"type": "noop", "target": None}

            return action
                
        except Exception as e:
            logger.error(f"Agent decision failed: {e}")
            return {"type": "noop", "target": None}

    def _normalize_observation(self, observation: Any) -> Dict[str, Any]:
        if hasattr(observation, "queues"):
            queues = getattr(observation, "queues", {}) or {}
            capacities = getattr(observation, "capacities", {}) or {}
            system_pressure = float(getattr(observation, "system_pressure", 0.0) or 0.0)
            retry_rate = float(getattr(observation, "retry_rate", 0.0) or 0.0)
            error_rate = float(getattr(observation, "error_rate", 0.0) or 0.0)
        elif isinstance(observation, dict):
            queues = observation.get("queues", {}) or {}
            capacities = observation.get("capacities", {}) or {}
            system_pressure = float(observation.get("system_pressure", 0.0) or 0.0)
            retry_rate = float(observation.get("retry_rate", 0.0) or 0.0)
            error_rate = float(observation.get("error_rate", 0.0) or 0.0)
        else:
            queues = {}
            capacities = {}
            system_pressure = 0.0
            retry_rate = 0.0
            error_rate = 0.0

        return {
            "queues": {queue: float(value or 0.0) for queue, value in queues.items()},
            "capacities": {
                queue: max(float(value or 0.0), 1.0)
                for queue, value in capacities.items()
            },
            "system_pressure": system_pressure,
            "retry_rate": retry_rate,
            "error_rate": error_rate,
        }

    def _queue_ratios(self, snapshot: Dict[str, Any]) -> Dict[str, float]:
        queues = snapshot["queues"]
        capacities = snapshot["capacities"]
        return {
            queue: queues.get(queue, 0.0) / max(capacities.get(queue, 1.0), 1.0)
            for queue in queues
        }

    def _worst_queue(self, snapshot: Dict[str, Any]) -> str:
        ratios = self._queue_ratios(snapshot)
        if not ratios:
            return "A"

        return max(
            ratios,
            key=lambda queue: (
                ratios[queue],
                snapshot["queues"].get(queue, 0.0),
            ),
        )

    def _adaptive_strategy(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        """Adaptive strategy that responds to current conditions."""
        max_ratio = max(self._queue_ratios(snapshot).values(), default=0.0)
        target = self._worst_queue(snapshot)
        pressure = snapshot["system_pressure"]

<<<<<<< HEAD
        if max_ratio >= 2.0 or pressure >= 2.2:
            return {"type": "restart", "target": target}

        if max_ratio >= 0.95 or pressure >= 1.0:
            return {"type": "scale", "target": target}

        if max_ratio >= 0.65 and (snapshot["retry_rate"] >= 0.35 or snapshot["error_rate"] >= 0.25):
=======
        # Aggressive restart for critical overload
        if max_ratio >= 1.8 or pressure >= 2.0:
            return {"type": "restart", "target": target}

        # Scale for high utilization
        if max_ratio >= 0.85 or pressure >= 0.95:
            return {"type": "scale", "target": target}

        # Throttle for moderate pressure with error/retry spikes
        if max_ratio >= 0.55 and (snapshot["retry_rate"] >= 0.3 or snapshot["error_rate"] >= 0.2):
            return {"type": "throttle", "target": target}

        # Proactive throttle for building pressure
        if max_ratio >= 0.45 and pressure >= 0.7:
>>>>>>> 3f8b51ce07d34fbefba8a351d57cc42f33924908
            return {"type": "throttle", "target": target}

        return {"type": "noop", "target": None}
    
    def _conservative_strategy(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        """Conservative strategy - only act in emergencies."""
        max_ratio = max(self._queue_ratios(snapshot).values(), default=0.0)
        target = self._worst_queue(snapshot)
        pressure = snapshot["system_pressure"]

<<<<<<< HEAD
        if max_ratio >= 3.0 or pressure >= 2.8:
            return {"type": "restart", "target": target}

        if max_ratio >= 1.5 or pressure >= 1.7:
            return {"type": "scale", "target": target}

=======
        # Emergency restart
        if max_ratio >= 2.5 or pressure >= 2.5:
            return {"type": "restart", "target": target}

        # High pressure scale
        if max_ratio >= 1.3 or pressure >= 1.5:
            return {"type": "scale", "target": target}

        # Moderate throttle
        if max_ratio >= 0.9 or pressure >= 1.2:
            return {"type": "throttle", "target": target}

>>>>>>> 3f8b51ce07d34fbefba8a351d57cc42f33924908
        return {"type": "noop", "target": None}
    
    def _aggressive_strategy(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        """Aggressive strategy - acts on any imbalance."""
        max_ratio = max(self._queue_ratios(snapshot).values(), default=0.0)
        target = self._worst_queue(snapshot)
        pressure = snapshot["system_pressure"]

<<<<<<< HEAD
        if max_ratio >= 2.5 or pressure >= 2.4:
            return {"type": "restart", "target": target}

        if max_ratio >= 0.75 or pressure >= 0.9:
            return {"type": "throttle", "target": target}

        if max_ratio >= 0.35 or pressure >= 0.5:
            return {"type": "scale", "target": target}

=======
        # Restart for high overload
        if max_ratio >= 2.0 or pressure >= 2.2:
            return {"type": "restart", "target": target}

        # Scale for moderate-high pressure
        if max_ratio >= 0.65 or pressure >= 0.85:
            return {"type": "scale", "target": target}

        # Throttle for any building pressure
        if max_ratio >= 0.3 or pressure >= 0.45:
            return {"type": "throttle", "target": target}

>>>>>>> 3f8b51ce07d34fbefba8a351d57cc42f33924908
        return {"type": "noop", "target": None}


class LearningAgent:
<<<<<<< HEAD
    """State-aware learning agent backed by a lightweight Q-table."""

    def __init__(
        self,
        alpha: float = 0.3,
        alpha_decay: float = 0.999,
        min_alpha: float = 0.05,
        gamma: float = 0.9,
        epsilon: float = 0.2,
        epsilon_decay: float = 0.995,
        min_epsilon: float = 0.02,
        max_states: int = 500,
=======
    """State-aware learning agent backed by an improved Q-learning algorithm."""

    def __init__(
        self,
        alpha: float = 0.4,
        alpha_decay: float = 0.998,
        min_alpha: float = 0.08,
        gamma: float = 0.95,
        epsilon: float = 0.25,
        epsilon_decay: float = 0.993,
        min_epsilon: float = 0.05,
        max_states: int = 1000,
>>>>>>> 3f8b51ce07d34fbefba8a351d57cc42f33924908
        seed: int = 0,
    ):
        self.initial_alpha = float(alpha)
        self.alpha = float(alpha)
        self.alpha_decay = float(alpha_decay)
        self.min_alpha = float(min_alpha)
        self.gamma = float(gamma)
        self.initial_epsilon = float(epsilon)
        self.epsilon = float(epsilon)
        self.epsilon_decay = float(epsilon_decay)
        self.min_epsilon = float(min_epsilon)
        self.max_states = int(max_states)
        self.rng = random.Random(seed)
<<<<<<< HEAD
        self.memory: List[tuple[tuple[float, str], Dict[str, Any], float]] = []
        self.q_table: Dict[tuple[float, str], Dict[str, float]] = {}
        self.state_order: List[tuple[float, str]] = []
        self.last_state_signature: Optional[tuple[float, str]] = None
        self.name = "Simple-learning"
=======
        self.memory: List[tuple[tuple[float, str, str], Dict[str, Any], float]] = []
        self.q_table: Dict[tuple[float, str, str], Dict[str, float]] = {}
        self.state_order: List[tuple[float, str, str]] = []
        self.last_state_signature: Optional[tuple[float, str, str]] = None
        self.name = "Simple-learning"
        self.episode_count = 0
        self.step_count = 0
>>>>>>> 3f8b51ce07d34fbefba8a351d57cc42f33924908

    def act(self, observation: Any) -> Dict[str, Any]:
        snapshot = self._normalize_observation(observation)
        self.last_state_signature = self._state_signature(snapshot)
        action = self._best_known_action(snapshot)
<<<<<<< HEAD
=======
        self.step_count += 1
>>>>>>> 3f8b51ce07d34fbefba8a351d57cc42f33924908
        self.epsilon = max(self.min_epsilon, self.epsilon * self.epsilon_decay)
        self.alpha = max(self.min_alpha, self.alpha * self.alpha_decay)
        return action

    def observe(
        self,
        action: Dict[str, Any],
        reward: float,
        observation: Any = None,
        next_observation: Any = None,
    ):
        snapshot = self._normalize_observation(observation) if observation is not None else None
        next_snapshot = self._normalize_observation(next_observation) if next_observation is not None else None
        state_signature = (
            self._state_signature(snapshot)
            if snapshot is not None
            else self.last_state_signature
        )
        normalized_action = self._normalize_action(action)

        if not state_signature:
            return

        if state_signature not in self.q_table:
            self._register_state(state_signature)

        action_key = self._action_key(normalized_action)
        state_actions = self.q_table.setdefault(state_signature, {})
        current_value = float(state_actions.get(action_key, 0.5))

<<<<<<< HEAD
=======
        # Compute TD target with better bootstrapping
>>>>>>> 3f8b51ce07d34fbefba8a351d57cc42f33924908
        next_best = 0.5
        if next_snapshot is not None:
            next_state_signature = self._state_signature(next_snapshot)
            if next_state_signature not in self.q_table:
                self._register_state(next_state_signature)
            next_actions = self.q_table.get(next_state_signature, {})
            next_best = max(next_actions.values(), default=0.5)

<<<<<<< HEAD
        td_target = float(reward) + self.gamma * next_best
        updated_value = current_value + self.alpha * (td_target - current_value)
=======
        # TD update with adaptive learning rate based on reward magnitude
        reward_magnitude = abs(float(reward))
        adaptive_alpha = self.alpha * (1.0 + 0.2 * min(reward_magnitude, 2.0))
        
        td_target = float(reward) + self.gamma * next_best
        td_error = td_target - current_value
        updated_value = current_value + adaptive_alpha * td_error
>>>>>>> 3f8b51ce07d34fbefba8a351d57cc42f33924908
        state_actions[action_key] = updated_value

        self.memory.append((state_signature, normalized_action, float(reward)))
        self.memory = self.memory[-self.max_states:]

    def _best_known_action(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        state_signature = self._state_signature(snapshot)
        possible_actions = self._get_possible_actions(snapshot)

<<<<<<< HEAD
        if self.rng.random() < self.epsilon:
=======
        # Epsilon-greedy with pressure-aware exploration
        pressure = float(snapshot.get("system_pressure", 0.0) or 0.0)
        exploration_rate = self.epsilon
        if pressure > 2.0:
            exploration_rate *= 0.5  # Less exploration in crisis
        elif pressure < 0.5:
            exploration_rate *= 1.2  # More exploration in calm

        if self.rng.random() < exploration_rate:
>>>>>>> 3f8b51ce07d34fbefba8a351d57cc42f33924908
            return deepcopy(self.rng.choice(possible_actions))

        known_actions = self.q_table.get(state_signature, {})
        if not known_actions:
            return {"type": "noop", "target": None}

        best_action: Dict[str, Any] | None = None
        best_value = float("-inf")
        for action in possible_actions:
            action_key = self._action_key(action)
            score = float(known_actions.get(action_key, 0.0))
            if score > best_value:
                best_value = score
                best_action = action

        if best_action is None or best_value <= 0.0:
            return {"type": "noop", "target": None}

        return deepcopy(best_action)

    def reset(self):
        self.memory = []
        self.q_table = {}
        self.state_order = []
        self.last_state_signature = None
        self.epsilon = self.initial_epsilon
        self.alpha = self.initial_alpha
<<<<<<< HEAD
=======
        self.episode_count += 1
>>>>>>> 3f8b51ce07d34fbefba8a351d57cc42f33924908

    def _normalize_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        action_type = str(action.get("type", action.get("action_type", "noop"))).lower()
        if action_type == "noop":
            return {"type": "noop", "target": None}

        return {
            "type": action_type,
            "target": action.get("target"),
        }

    def _normalize_observation(self, observation: Any) -> Dict[str, Any]:
        if hasattr(observation, "queues"):
            queues = getattr(observation, "queues", {}) or {}
            capacities = getattr(observation, "capacities", {}) or {}
            system_pressure = float(getattr(observation, "system_pressure", 0.0) or 0.0)
<<<<<<< HEAD
=======
            retry_rate = float(getattr(observation, "retry_rate", 0.0) or 0.0)
            error_rate = float(getattr(observation, "error_rate", 0.0) or 0.0)
>>>>>>> 3f8b51ce07d34fbefba8a351d57cc42f33924908
        elif isinstance(observation, dict):
            queues = observation.get("queues", {}) or {}
            capacities = observation.get("capacities", {}) or {}
            system_pressure = float(
                observation.get("system_pressure", observation.get("pressure", 0.0)) or 0.0
            )
<<<<<<< HEAD
=======
            retry_rate = float(observation.get("retry_rate", 0.0) or 0.0)
            error_rate = float(observation.get("error_rate", 0.0) or 0.0)
>>>>>>> 3f8b51ce07d34fbefba8a351d57cc42f33924908
        else:
            queues = {}
            capacities = {}
            system_pressure = 0.0
<<<<<<< HEAD
=======
            retry_rate = 0.0
            error_rate = 0.0
>>>>>>> 3f8b51ce07d34fbefba8a351d57cc42f33924908

        normalized_queues = {
            str(queue): float(value or 0.0)
            for queue, value in queues.items()
        }
        normalized_capacities = {
            str(queue): max(float(value or 0.0), 1.0)
            for queue, value in capacities.items()
        }

        return {
            "queues": normalized_queues,
            "capacities": normalized_capacities,
            "system_pressure": system_pressure,
<<<<<<< HEAD
        }

    def _state_signature(self, snapshot: Dict[str, Any]) -> tuple[float, str]:
        queues = snapshot.get("queues", {}) or {}
        rounded_pressure = round(float(snapshot.get("system_pressure", 0.0) or 0.0), 1)
=======
            "retry_rate": retry_rate,
            "error_rate": error_rate,
        }

    def _state_signature(self, snapshot: Dict[str, Any]) -> tuple[float, str, str]:
        """Enhanced state signature with retry/error awareness."""
        queues = snapshot.get("queues", {}) or {}
        pressure = float(snapshot.get("system_pressure", 0.0) or 0.0)
        retry_rate = float(snapshot.get("retry_rate", 0.0) or 0.0)
        error_rate = float(snapshot.get("error_rate", 0.0) or 0.0)
        
        # Quantize pressure into buckets
        pressure_bucket = round(pressure * 2) / 2  # 0.5 granularity
        
        # Identify bottleneck queue
>>>>>>> 3f8b51ce07d34fbefba8a351d57cc42f33924908
        bottleneck = max(
            queues,
            key=lambda queue: float(queues.get(queue, 0.0) or 0.0),
            default="A",
        )
<<<<<<< HEAD
        return (rounded_pressure, str(bottleneck))
=======
        
        # Encode error/retry state
        error_state = "high" if (retry_rate > 0.5 or error_rate > 0.3) else "normal"
        
        return (pressure_bucket, str(bottleneck), error_state)
>>>>>>> 3f8b51ce07d34fbefba8a351d57cc42f33924908

    def _get_possible_actions(self, snapshot: Dict[str, Any]) -> List[Dict[str, Any]]:
        queue_targets = sorted((snapshot.get("queues", {}) or {}).keys()) or ["A", "B", "C"]
        actions: List[Dict[str, Any]] = [{"type": "noop", "target": None}]
        for queue in queue_targets:
            actions.extend([
                {"type": "restart", "target": queue},
                {"type": "scale", "target": queue},
                {"type": "throttle", "target": queue},
            ])
        return actions

    def _action_key(self, action: Dict[str, Any]) -> str:
        normalized_action = self._normalize_action(action)
        return f"{normalized_action['type']}:{normalized_action.get('target') or 'none'}"

<<<<<<< HEAD
    def _register_state(self, state_signature: tuple[float, str]) -> None:
=======
    def _register_state(self, state_signature: tuple[float, str, str]) -> None:
>>>>>>> 3f8b51ce07d34fbefba8a351d57cc42f33924908
        if state_signature in self.q_table:
            return

        if len(self.q_table) >= self.max_states and self.state_order:
            oldest_state = self.state_order.pop(0)
            self.q_table.pop(oldest_state, None)

        self.state_order.append(state_signature)


class MetricsTracker:
    """Metrics tracker for live agent evaluation."""
    
    def __init__(self):
        self.total_reward = 0.0
        self.total_actions = 0
        self.necessary_actions = 0
        self.positive_impacts = 0
        self.total_impact = 0.0
        self.trajectory = []
    
    def update(self, reward: float, action: Dict[str, Any], info: Dict[str, Any]):
        """Update metrics with new step."""
        self.total_reward += reward
        self.trajectory.append({
            'reward': reward,
            'action': action,
            'info': info
        })
        
        # Count non-noop actions
        if action.get('type') != 'noop':
            self.total_actions += 1
            
            # Check if action was necessary
            if info.get('was_action_necessary', False):
                self.necessary_actions += 1
            
            # Check positive impact
            impact = info.get('counterfactual_impact', 0)
            self.total_impact += impact
            if info.get('had_meaningful_impact', False):
                self.positive_impacts += 1
    
    def get_metrics(self) -> Dict[str, float]:
        """Get current metrics."""
        necessary_ratio = (
            self.necessary_actions / self.total_actions 
            if self.total_actions > 0 else 0.0
        )
        positive_ratio = (
            self.positive_impacts / self.total_actions 
            if self.total_actions > 0 else 0.0
        )
        average_impact = (
            self.total_impact / self.total_actions
            if self.total_actions > 0 else 0.0
        )
        
        return {
            'total_reward': round(self.total_reward, 4),
            'necessary_action_ratio': round(necessary_ratio, 4),
            'positive_impact_rate': round(positive_ratio, 4),
            'average_impact': round(average_impact, 4),
            'total_actions': self.total_actions,
            'necessary_actions': self.necessary_actions,
            'positive_impacts': self.positive_impacts,
            'total_impact': round(self.total_impact, 4),
        }
    
    def reset(self):
        """Reset all metrics."""
        self.total_reward = 0.0
        self.total_actions = 0
        self.necessary_actions = 0
        self.positive_impacts = 0
        self.total_impact = 0.0
        self.trajectory = []


# Global metrics tracker
metrics_tracker = MetricsTracker()

<<<<<<< HEAD
def _make_cf_planner() -> Any:
    from env.environment import ASCDCEnvironment
    return CounterfactualPlannerAgent(ASCDCEnvironment())


=======
>>>>>>> 3f8b51ce07d34fbefba8a351d57cc42f33924908
AGENT_FACTORIES: Dict[str, Callable[[], Any]] = {
    "simple-adaptive": lambda: SimpleAgent("adaptive"),
    "strong-decision": SmartAgent,
    "simple-learning": LearningAgent,
    "simple-conservative": lambda: SimpleAgent("conservative"),
    "simple-aggressive": lambda: SimpleAgent("aggressive"),
<<<<<<< HEAD
    "cf-planner": _make_cf_planner,
=======
>>>>>>> 3f8b51ce07d34fbefba8a351d57cc42f33924908
}

# Available agents
AVAILABLE_AGENTS = {
    agent_name: factory()
    for agent_name, factory in AGENT_FACTORIES.items()
}

# Current active agent
current_agent_name = "simple-adaptive"
current_agent: Any = AVAILABLE_AGENTS[current_agent_name]


def get_current_agent() -> Any:
    """Get the currently active agent."""
    return current_agent


def get_current_agent_name() -> str:
    """Get the current agent identifier."""
    return current_agent_name


def set_agent(agent_name: str) -> bool:
    """Set the active agent by name."""
    global current_agent_name, current_agent
    
    if agent_name not in AVAILABLE_AGENTS:
        logger.error(f"Unknown agent: {agent_name}")
        return False
    
    current_agent_name = agent_name
    current_agent = AVAILABLE_AGENTS[agent_name]
    metrics_tracker.reset()
    if hasattr(current_agent, "reset"):
        current_agent.reset()
    logger.info(f"Switched to agent: {agent_name}")
    return True


def get_available_agents() -> List[str]:
    """Get list of available agent names."""
    return list(AVAILABLE_AGENTS.keys())


def create_agent(agent_name: str) -> Any:
    """Create a fresh agent instance by name."""
    factory = AGENT_FACTORIES.get(agent_name)
    if factory is None:
        raise KeyError(f"Unknown agent: {agent_name}")
    return factory()


def get_metrics() -> Dict[str, float]:
    """Get current metrics."""
    return metrics_tracker.get_metrics()


def update_metrics(
    reward: float,
    action: Dict[str, Any],
    info: Dict[str, Any],
    observation: Any = None,
    next_observation: Any = None,
):
    """Update metrics with new step."""
    metrics_tracker.update(reward, action, info)
    if hasattr(current_agent, "observe"):
        current_agent.observe(
            action,
            reward,
            observation=observation,
            next_observation=next_observation,
        )


def reset_metrics():
    """Reset metrics."""
    metrics_tracker.reset()
    if hasattr(current_agent, "reset"):
        current_agent.reset()
