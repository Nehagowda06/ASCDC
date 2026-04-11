"""Agent implementations for ASCDC."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable, Dict, List, Optional
import logging
import random

from core.agents.smart_agent import SmartAgent

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

        if max_ratio >= 2.0 or pressure >= 2.2:
            return {"type": "restart", "target": target}

        if max_ratio >= 0.95 or pressure >= 1.0:
            return {"type": "scale", "target": target}

        if max_ratio >= 0.65 and (snapshot["retry_rate"] >= 0.35 or snapshot["error_rate"] >= 0.25):
            return {"type": "throttle", "target": target}

        return {"type": "noop", "target": None}
    
    def _conservative_strategy(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        """Conservative strategy - only act in emergencies."""
        max_ratio = max(self._queue_ratios(snapshot).values(), default=0.0)
        target = self._worst_queue(snapshot)
        pressure = snapshot["system_pressure"]

        if max_ratio >= 3.0 or pressure >= 2.8:
            return {"type": "restart", "target": target}

        if max_ratio >= 1.5 or pressure >= 1.7:
            return {"type": "scale", "target": target}

        return {"type": "noop", "target": None}
    
    def _aggressive_strategy(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        """Aggressive strategy - acts on any imbalance."""
        max_ratio = max(self._queue_ratios(snapshot).values(), default=0.0)
        target = self._worst_queue(snapshot)
        pressure = snapshot["system_pressure"]

        if max_ratio >= 2.5 or pressure >= 2.4:
            return {"type": "restart", "target": target}

        if max_ratio >= 0.75 or pressure >= 0.9:
            return {"type": "throttle", "target": target}

        if max_ratio >= 0.35 or pressure >= 0.5:
            return {"type": "scale", "target": target}

        return {"type": "noop", "target": None}


class LearningAgent:
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
        self.memory: List[tuple[tuple[float, str], Dict[str, Any], float]] = []
        self.q_table: Dict[tuple[float, str], Dict[str, float]] = {}
        self.state_order: List[tuple[float, str]] = []
        self.last_state_signature: Optional[tuple[float, str]] = None
        self.name = "Simple-learning"
        
        # Firestorm enhancements
        self.emergency_threshold = 2.5  # System pressure threshold for emergency mode
        self.crisis_learning_boost = 2.0  # Learning rate multiplier in crisis
        self.high_pressure_explore_reduction = 0.3  # Reduce exploration in firestorm
        self.recent_rewards: List[float] = []  # Track recent performance
        self.streak_counter = 0  # Track consecutive good/bad decisions

    def act(self, observation: Any) -> Dict[str, Any]:
        snapshot = self._normalize_observation(observation)
        self.last_state_signature = self._state_signature(snapshot)
        
        # Pure Q-learning action selection - no heuristic overrides
        action = self._best_known_action(snapshot)
            
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

        next_best = 0.5
        if next_snapshot is not None:
            next_state_signature = self._state_signature(next_snapshot)
            if next_state_signature not in self.q_table:
                self._register_state(next_state_signature)
            next_actions = self.q_table.get(next_state_signature, {})
            next_best = max(next_actions.values(), default=0.5)

        # Pure Q-learning update - no adaptive rate manipulation
        td_target = float(reward) + self.gamma * next_best
        td_error = td_target - current_value
        updated_value = current_value + self.alpha * td_error
        state_actions[action_key] = updated_value
        
        # Track learning progress
        self.recent_rewards.append(float(reward))
        self.recent_rewards = self.recent_rewards[-10:]  # Keep last 10 rewards
        
        # Log learning statistics periodically
        if len(self.memory) % 50 == 0:
            avg_reward = sum(self.recent_rewards) / len(self.recent_rewards) if self.recent_rewards else 0
            print(f"LearningAgent - States learned: {len(self.q_table)}, Recent avg reward: {avg_reward:.3f}")

        self.memory.append((state_signature, normalized_action, float(reward)))
        self.memory = self.memory[-self.max_states:]

    def _best_known_action(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        state_signature = self._state_signature(snapshot)
        possible_actions = self._get_possible_actions(snapshot)
        
        # Pure epsilon-greedy exploration - no pressure-based manipulation
        if self.rng.random() < self.epsilon:
            return deepcopy(self.rng.choice(possible_actions))

        known_actions = self.q_table.get(state_signature, {})
        if not known_actions:
            # Initialize Q-values for new state
            self._register_state(state_signature)
            known_actions = self.q_table.get(state_signature, {})

        best_action: Dict[str, Any] | None = None
        best_value = float("-inf")
        for action in possible_actions:
            action_key = self._action_key(action)
            # Use pure Q-values - no heuristic bonuses
            score = float(known_actions.get(action_key, 0.0))
            if score > best_value:
                best_value = score
                best_action = action

        if best_action is None:
            return {"type": "noop", "target": None}

        return deepcopy(best_action)

    def _get_learning_stats(self) -> Dict[str, float]:
        """Get learning statistics for monitoring."""
        avg_reward = sum(self.recent_rewards) / len(self.recent_rewards) if self.recent_rewards else 0
        return {
            "states_learned": len(self.q_table),
            "recent_avg_reward": avg_reward,
            "epsilon": self.epsilon,
            "alpha": self.alpha,
            "memory_size": len(self.memory)
        }

    def reset(self):
        self.memory = []
        self.q_table = {}
        self.state_order = []
        self.last_state_signature = None
        self.epsilon = self.initial_epsilon
        self.alpha = self.initial_alpha
        self.recent_rewards = []
        self.streak_counter = 0

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
        elif isinstance(observation, dict):
            queues = observation.get("queues", {}) or {}
            capacities = observation.get("capacities", {}) or {}
            system_pressure = float(
                observation.get("system_pressure", observation.get("pressure", 0.0)) or 0.0
            )
        else:
            queues = {}
            capacities = {}
            system_pressure = 0.0

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
        }

    def _state_signature(self, snapshot: Dict[str, Any]) -> tuple[float, str]:
        queues = snapshot.get("queues", {}) or {}
        system_pressure = float(snapshot.get("system_pressure", 0.0) or 0.0)
        instability = float(snapshot.get("instability_score", 0.0) or 0.0)
        
        # Better state representation for learning - more granular pressure
        pressure_bucket = round(system_pressure * 2) / 2  # 0.5 granularity
        
        # Find bottleneck queue
        bottleneck = max(
            queues,
            key=lambda queue: float(queues.get(queue, 0.0) or 0.0),
            default="A",
        )
        
        # Include queue utilization ratio for better state discrimination
        bottleneck_util = float(queues.get(bottleneck, 0.0))
        util_category = "low" if bottleneck_util < 5.0 else "med" if bottleneck_util < 15.0 else "high"
        
        # Include instability for learning to recognize firestorm states
        instability_bucket = "low" if instability < 0.3 else "med" if instability < 1.0 else "high"
        
        return (pressure_bucket, f"{str(bottleneck)}_{util_category}_{instability_bucket}")

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

    def _register_state(self, state_signature: tuple[float, str]) -> None:
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


AGENT_FACTORIES: Dict[str, Callable[[], Any]] = {
    "simple-adaptive": lambda: SimpleAgent("adaptive"),
    "strong-decision": SmartAgent,
    "simple-learning": LearningAgent,
    "simple-conservative": lambda: SimpleAgent("conservative"),
    "simple-aggressive": lambda: SimpleAgent("aggressive"),
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
