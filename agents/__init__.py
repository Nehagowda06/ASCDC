"""
Agent system initialization
"""

from .simple_agent import (
    SimpleAgent,
    MetricsTracker,
    get_current_agent,
    get_current_agent_name,
    set_agent,
    get_available_agents,
    get_metrics,
    update_metrics,
    reset_metrics,
    AVAILABLE_AGENTS
)

__all__ = [
    "SimpleAgent",
    "MetricsTracker", 
    "get_current_agent",
    "get_current_agent_name",
    "set_agent",
    "get_available_agents",
    "get_metrics",
    "update_metrics",
    "reset_metrics",
    "AVAILABLE_AGENTS"
]
