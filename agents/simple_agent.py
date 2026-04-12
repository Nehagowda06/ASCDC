"""Agent implementations for ASCDC."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple
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
    requires_env = True

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
        rollout_horizon: int = 5,
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
        self.rollout_horizon = max(2, int(rollout_horizon))
        self.rng = random.Random(seed)
        self.memory: List[tuple[tuple[float, str], Dict[str, Any], float]] = []
        self.q_table: Dict[tuple[float, str], Dict[str, float]] = {}
        self.state_order: List[tuple[float, str]] = []
        self.last_state_signature: Optional[tuple[float, str]] = None
        self.name = "Simple-learning"
        self.teacher = SmartAgent(horizon=8)
        
        # Firestorm enhancements
        self.emergency_threshold = 2.5  # System pressure threshold for emergency mode
        self.crisis_learning_boost = 2.0  # Learning rate multiplier in crisis
        self.high_pressure_explore_reduction = 0.3  # Reduce exploration in firestorm
        self.recent_rewards: List[float] = []  # Track recent performance
        self.streak_counter = 0  # Track consecutive good/bad decisions
        self.expert_bootstrap_steps = 40
        self.expert_bonus = 1.5

    def act(self, observation: Any) -> Dict[str, Any]:
        snapshot = self._normalize_observation(observation)
        self.last_state_signature = self._state_signature(snapshot)
        self._register_state(self.last_state_signature, snapshot)
        effective_epsilon = self._effective_epsilon(snapshot)
        teacher_action: Optional[Dict[str, Any]] = None
        use_teacher = (
            float(snapshot.get("system_pressure", 0.0) or 0.0) >= self.emergency_threshold
            or len(self.memory) < self.expert_bootstrap_steps
        )

        if hasattr(observation, "clone") and callable(getattr(observation, "clone")):
            if use_teacher:
                teacher_action = self.teacher.act(observation)
                if self.rng.random() >= effective_epsilon:
                    action = deepcopy(teacher_action)
                else:
                    action = self._rollout_guided_action(
                        observation,
                        snapshot,
                        effective_epsilon,
                        teacher_action,
                    )
            else:
                action = self._rollout_guided_action(observation, snapshot, effective_epsilon, teacher_action)
        else:
            action = self._best_known_action(snapshot, effective_epsilon)
            
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

        self._register_state(state_signature, snapshot)

        action_key = self._action_key(normalized_action)
        state_actions = self.q_table.setdefault(state_signature, {})
        current_value = float(state_actions.get(action_key, 0.0))

        next_best = 0.0
        if next_snapshot is not None:
            next_state_signature = self._state_signature(next_snapshot)
            self._register_state(next_state_signature, next_snapshot)
            next_actions = self.q_table.get(next_state_signature, {})
            next_best = max(next_actions.values(), default=0.0)

        td_target = float(reward) + self.gamma * next_best
        td_error = td_target - current_value
        crisis_multiplier = (
            self.crisis_learning_boost
            if (
                (snapshot and float(snapshot.get("system_pressure", 0.0) or 0.0) >= self.emergency_threshold)
                or (snapshot and float(snapshot.get("instability_score", 0.0) or 0.0) >= 1.0)
            )
            else 1.0
        )
        effective_alpha = min(0.8, self.alpha * crisis_multiplier)
        updated_value = current_value + effective_alpha * td_error
        state_actions[action_key] = updated_value
        
        # Track learning progress
        self.recent_rewards.append(float(reward))
        self.recent_rewards = self.recent_rewards[-10:]  # Keep last 10 rewards
        
        if self.memory and len(self.memory) % 50 == 0:
            avg_reward = sum(self.recent_rewards) / len(self.recent_rewards) if self.recent_rewards else 0
            print(f"LearningAgent - States learned: {len(self.q_table)}, Recent avg reward: {avg_reward:.3f}")

        self.memory.append((state_signature, normalized_action, float(reward)))
        self.memory = self.memory[-self.max_states:]

    def _best_known_action(
        self,
        snapshot: Dict[str, Any],
        effective_epsilon: Optional[float] = None,
    ) -> Dict[str, Any]:
        state_signature = self._state_signature(snapshot)
        possible_actions = self._get_possible_actions(snapshot)
        effective_epsilon = (
            self._effective_epsilon(snapshot)
            if effective_epsilon is None
            else float(effective_epsilon)
        )
        if self.rng.random() < effective_epsilon:
            ranked = sorted(
                possible_actions,
                key=lambda action: self.q_table.get(state_signature, {}).get(
                    self._action_key(action),
                    self._action_priors(snapshot).get(self._action_key(action), 0.0),
                ),
                reverse=True,
            )
            explore_pool = ranked[: min(3, len(ranked))]
            return deepcopy(self.rng.choice(explore_pool))

        known_actions = self.q_table.get(state_signature, {})
        if not known_actions:
            self._register_state(state_signature, snapshot)
            known_actions = self.q_table.get(state_signature, {})

        best_action: Dict[str, Any] | None = None
        best_value = float("-inf")
        for action in possible_actions:
            action_key = self._action_key(action)
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
        self.teacher = SmartAgent(horizon=8)

    def _normalize_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        action_type = str(action.get("type", action.get("action_type", "noop"))).lower()
        if action_type == "noop":
            return {"type": "noop", "target": None}

        return {
            "type": action_type,
            "target": action.get("target"),
        }

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
            "system_pressure": float(snapshot.get("system_pressure", snapshot.get("pressure", 0.0)) or 0.0),
            "instability_score": float(snapshot.get("instability_score", 0.0) or 0.0),
            "retry_rate": float(snapshot.get("retry_rate", 0.0) or 0.0),
            "error_rate": float(snapshot.get("error_rate", 0.0) or 0.0),
            "latencies": {
                str(queue): float(value or 0.0)
                for queue, value in (snapshot.get("latencies", {}) or {}).items()
            },
            "base_load": {
                str(queue): float(value or 0.0)
                for queue, value in (snapshot.get("base_load", {}) or {}).items()
            },
            "active_locks": deepcopy(snapshot.get("active_locks", {}) or {}),
            "pending_actions": deepcopy(snapshot.get("pending_actions", []) or []),
        }

    def _state_signature(self, snapshot: Dict[str, Any]) -> tuple[float, str]:
        queues = snapshot.get("queues", {}) or {}
        capacities = snapshot.get("capacities", {}) or {}
        system_pressure = float(snapshot.get("system_pressure", 0.0) or 0.0)
        instability = float(snapshot.get("instability_score", 0.0) or 0.0)
        active_locks = snapshot.get("active_locks", {}) or {}

        pressure_bucket = round(system_pressure * 2) / 2
        bottleneck = max(
            queues,
            key=lambda queue: (
                float(queues.get(queue, 0.0) or 0.0) / max(float(capacities.get(queue, 1.0) or 1.0), 1.0),
                float(queues.get(queue, 0.0) or 0.0),
            ),
            default="A",
        )
        bottleneck_ratio = float(queues.get(bottleneck, 0.0) or 0.0) / max(
            float(capacities.get(bottleneck, 1.0) or 1.0),
            1.0,
        )
        util_category = "low" if bottleneck_ratio < 0.5 else "med" if bottleneck_ratio < 1.5 else "high"
        instability_bucket = "low" if instability < 0.3 else "med" if instability < 1.0 else "high"
        lock_bucket = "locked" if active_locks else "open"

        return (pressure_bucket, f"{str(bottleneck)}_{util_category}_{instability_bucket}_{lock_bucket}")

    def _get_possible_actions(self, snapshot: Dict[str, Any]) -> List[Dict[str, Any]]:
        queue_targets = sorted((snapshot.get("queues", {}) or {}).keys()) or ["A", "B", "C"]
        active_locks = snapshot.get("active_locks", {}) or {}
        actions: List[Dict[str, Any]] = [{"type": "noop", "target": None}]
        for queue in queue_targets:
            if queue in active_locks:
                continue
            actions.extend([
                {"type": "restart", "target": queue},
                {"type": "scale", "target": queue},
                {"type": "throttle", "target": queue},
            ])
        return actions

    def _action_key(self, action: Dict[str, Any]) -> str:
        normalized_action = self._normalize_action(action)
        return f"{normalized_action['type']}:{normalized_action.get('target') or 'none'}"

    def _register_state(
        self,
        state_signature: tuple[float, str],
        snapshot: Optional[Dict[str, Any]] = None,
    ) -> None:
        if state_signature in self.q_table:
            return

        if len(self.q_table) >= self.max_states and self.state_order:
            oldest_state = self.state_order.pop(0)
            self.q_table.pop(oldest_state, None)

        self.state_order.append(state_signature)
        self.q_table[state_signature] = self._action_priors(snapshot or {})

    def _effective_epsilon(self, snapshot: Dict[str, Any]) -> float:
        pressure = float(snapshot.get("system_pressure", 0.0) or 0.0)
        instability = float(snapshot.get("instability_score", 0.0) or 0.0)
        effective = self.epsilon
        if pressure >= self.emergency_threshold or instability >= 1.0:
            effective *= self.high_pressure_explore_reduction
        return max(self.min_epsilon, effective)

    def _action_priors(self, snapshot: Dict[str, Any]) -> Dict[str, float]:
        priors: Dict[str, float] = {
            self._action_key({"type": "noop", "target": None}): 0.1,
        }
        ranked_targets = self._ranked_targets(snapshot)
        system_pressure = float(snapshot.get("system_pressure", 0.0) or 0.0)
        instability = float(snapshot.get("instability_score", 0.0) or 0.0)
        retry_rate = float(snapshot.get("retry_rate", 0.0) or 0.0)
        error_rate = float(snapshot.get("error_rate", 0.0) or 0.0)

        if system_pressure >= self.emergency_threshold or instability >= 1.0:
            priors[self._action_key({"type": "noop", "target": None})] = -1.25

        for index, (queue, urgency) in enumerate(ranked_targets):
            rank_bonus = 0.6 if index == 0 else 0.25
            priors[self._action_key({"type": "restart", "target": queue})] = (
                urgency * 0.6
                + rank_bonus
                + (0.7 if system_pressure >= 2.6 else 0.0)
            )
            priors[self._action_key({"type": "scale", "target": queue})] = (
                urgency * 0.55
                + rank_bonus
                + (0.45 if system_pressure >= 1.4 else 0.0)
            )
            priors[self._action_key({"type": "throttle", "target": queue})] = (
                urgency * 0.45
                + rank_bonus * 0.7
                + ((retry_rate + error_rate) * 0.8)
            )

        return priors

    def _ranked_targets(self, snapshot: Dict[str, Any]) -> List[Tuple[str, float]]:
        queues = snapshot.get("queues", {}) or {}
        capacities = snapshot.get("capacities", {}) or {}
        base_load = snapshot.get("base_load", {}) or {}
        latencies = snapshot.get("latencies", {}) or {}
        active_locks = snapshot.get("active_locks", {}) or {}
        pending_actions = snapshot.get("pending_actions", []) or []

        rankings: List[Tuple[str, float]] = []
        for queue in sorted(queues.keys() or ("A", "B", "C")):
            queue_level = float(queues.get(queue, 0.0) or 0.0)
            capacity = max(float(capacities.get(queue, 1.0) or 1.0), 1.0)
            queue_ratio = queue_level / capacity
            load_ratio = float(base_load.get(queue, 0.0) or 0.0) / capacity
            latency = float(latencies.get(queue, 0.0) or 0.0)
            pending_support = sum(
                1.0
                for item in pending_actions
                if item.get("target") == queue and item.get("type") in {"scale", "restart", "throttle"}
            )
            lock_penalty = 3.0 if queue in active_locks else 0.0
            urgency = (
                (queue_ratio * 1.8)
                + (max(load_ratio - 1.0, 0.0) * 2.2)
                + (queue_level * 0.08)
                + (latency * 0.2)
                - (pending_support * 0.35)
                - lock_penalty
            )
            rankings.append((queue, urgency))

        rankings.sort(key=lambda item: item[1], reverse=True)
        return rankings

    def _rollout_guided_action(
        self,
        env: Any,
        snapshot: Dict[str, Any],
        effective_epsilon: float,
        teacher_action: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        possible_actions = self._get_possible_actions(snapshot)
        state_signature = self._state_signature(snapshot)
        known_actions = self.q_table.get(state_signature, {})

        scored_actions = []
        for action in possible_actions:
            score = self._estimate_action_value(env, snapshot, action) + float(
                known_actions.get(self._action_key(action), 0.0)
            )
            if teacher_action is not None and self._action_key(action) == self._action_key(teacher_action):
                score += self.expert_bonus
            scored_actions.append((score, action))
        scored_actions.sort(key=lambda item: item[0], reverse=True)

        if self.rng.random() < effective_epsilon:
            explore_pool = [action for _, action in scored_actions[: min(3, len(scored_actions))]]
            return deepcopy(self.rng.choice(explore_pool))

        return deepcopy(scored_actions[0][1]) if scored_actions else {"type": "noop", "target": None}

    def _estimate_action_value(
        self,
        env: Any,
        snapshot: Dict[str, Any],
        action: Dict[str, Any],
    ) -> float:
        env_copy = env.clone()
        _, reward, done, info = env_copy.step(action, evaluate_counterfactual=False)
        score = float(reward)
        if info.get("action_rejected") and action.get("type") != "noop":
            return score - 3.0

        next_snapshot = self._normalize_observation(env_copy.state())
        if not done:
            followup = self._planner_followup(next_snapshot)
            _, reward2, _, info2 = env_copy.step(followup, evaluate_counterfactual=False)
            score += 0.8 * float(reward2)
            if info2.get("action_rejected") and followup.get("type") != "noop":
                score -= 1.75
            next_snapshot = self._normalize_observation(env_copy.state())

        final_pressure = float(next_snapshot.get("system_pressure", 0.0) or 0.0)
        final_instability = float(next_snapshot.get("instability_score", 0.0) or 0.0)
        max_queue_ratio = max(
            (
                float(next_snapshot.get("queues", {}).get(queue, 0.0) or 0.0)
                / max(float(next_snapshot.get("capacities", {}).get(queue, 1.0) or 1.0), 1.0)
            )
            for queue in (next_snapshot.get("queues", {}) or {"A": 0.0})
        )
        score += (float(snapshot.get("system_pressure", 0.0) or 0.0) - final_pressure) * 0.7
        score -= final_pressure * 0.8
        score -= final_instability * 1.0
        score -= max_queue_ratio * 0.7
        return score

    def _planner_followup(self, snapshot: Dict[str, Any]) -> Dict[str, Any]:
        ranked_targets = self._ranked_targets(snapshot)
        target = ranked_targets[0][0] if ranked_targets else "A"
        queues = snapshot.get("queues", {}) or {}
        capacities = snapshot.get("capacities", {}) or {}
        pressure = float(snapshot.get("system_pressure", 0.0) or 0.0)
        retry_rate = float(snapshot.get("retry_rate", 0.0) or 0.0)
        error_rate = float(snapshot.get("error_rate", 0.0) or 0.0)
        max_ratio = max(
            (
                float(queues.get(queue, 0.0) or 0.0)
                / max(float(capacities.get(queue, 1.0) or 1.0), 1.0)
            )
            for queue in (queues or {"A": 0.0})
        )

        if pressure >= 2.8 or max_ratio >= 2.0:
            return {"type": "restart", "target": target}
        if pressure >= 1.4 or max_ratio >= 1.0:
            return {"type": "scale", "target": target}
        if retry_rate >= 0.3 or error_rate >= 0.2:
            return {"type": "throttle", "target": target}
        return {"type": "noop", "target": None}


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
