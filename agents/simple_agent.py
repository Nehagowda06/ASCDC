"""
Simple, working agent system for ASCDC
"""

from __future__ import annotations

from typing import Any, Dict, List
import logging

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
                return self._adaptive_strategy(snapshot)
            elif self.strategy == "conservative":
                return self._conservative_strategy(snapshot)
            elif self.strategy == "aggressive":
                return self._aggressive_strategy(snapshot)
            else:
                return {"type": "noop", "target": None}
                
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

class MetricsTracker:
    """Simple metrics tracker that actually updates."""
    
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

# Available agents
AVAILABLE_AGENTS = {
    "simple-adaptive": SimpleAgent("adaptive"),
    "simple-conservative": SimpleAgent("conservative"), 
    "simple-aggressive": SimpleAgent("aggressive"),
}

# Current active agent
current_agent_name = "simple-adaptive"
current_agent = AVAILABLE_AGENTS[current_agent_name]

def get_current_agent() -> SimpleAgent:
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
    logger.info(f"Switched to agent: {agent_name}")
    return True

def get_available_agents() -> List[str]:
    """Get list of available agent names."""
    return list(AVAILABLE_AGENTS.keys())

def get_metrics() -> Dict[str, float]:
    """Get current metrics."""
    return metrics_tracker.get_metrics()

def update_metrics(reward: float, action: Dict[str, Any], info: Dict[str, Any]):
    """Update metrics with new step."""
    metrics_tracker.update(reward, action, info)

def reset_metrics():
    """Reset metrics."""
    metrics_tracker.reset()
