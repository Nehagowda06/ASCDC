from __future__ import annotations

from typing import Any, Dict, Mapping


PRESSURE_INCREASE_THRESHOLD = 0.12
SMALL_PRESSURE_THRESHOLD = 0.05
INTERVENTION_WINDOW_LOW = 1.2
INTERVENTION_WINDOW_HIGH = 2.5
PREMATURE_PRESSURE = 1.0
TOO_LATE_PRESSURE = 3.0
HIGH_INSTABILITY_THRESHOLD = 0.75


def clamp(value: float) -> float:
    """Clamp value to [0.0, 1.0] range."""
    return max(0.0, min(1.0, value))


def get_action_type(action: Any) -> str:
    """Extract action type from action dict or object."""
    if isinstance(action, Mapping):
        return str(action.get("type") or action.get("action_type") or "noop").lower()
    return str(getattr(action, "type", getattr(action, "action_type", "noop"))).lower()


def extract_pressure(state: Any) -> float:
    """Extract system pressure from state dict or object."""
    if isinstance(state, Mapping):
        value = state.get("system_pressure", state.get("pressure", 0.0))
        return float(value or 0.0)
    value = getattr(state, "system_pressure", getattr(state, "pressure", 0.0))
    return float(value or 0.0)


def extract_instability(state: Any) -> float:
    """Extract instability score from state dict or object."""
    if isinstance(state, Mapping):
        value = state.get("instability_score", 0.0)
        return float(value or 0.0)
    value = getattr(state, "instability_score", 0.0)
    return float(value or 0.0)


def evaluate_step_metrics(state: Any, action: Any, next_state: Any) -> Dict[str, Any]:
    """Evaluate step metrics: pressure delta, stability, necessity, timing.
    
    Computes multi-dimensional metrics for a single step including:
    - Pressure change and stability
    - Action necessity (based on pressure and instability)
    - Timing window (whether action was timely)
    
    Args:
        state: Current state dict or object
        action: Action dict or object
        next_state: Next state dict or object
        
    Returns:
        Dict with pressure, stability, necessity, timing_window, etc.
    """
    pressure = extract_pressure(state)
    next_pressure = extract_pressure(next_state)
    pressure_delta = next_pressure - pressure
    instability_score = max(extract_instability(state), extract_instability(next_state))
    action_type = get_action_type(action)
    acted = action_type != "noop"
    necessity = (
        pressure > INTERVENTION_WINDOW_LOW
        or pressure_delta > PRESSURE_INCREASE_THRESHOLD
        or instability_score >= HIGH_INSTABILITY_THRESHOLD
    )

    pressure_component = clamp(0.5 - (pressure_delta / 1.5))
    instability_component = clamp(1.0 - (instability_score / 4.0))
    stability = clamp(0.55 * pressure_component + 0.45 * instability_component)

    return {
        "pressure": pressure,
        "next_pressure": next_pressure,
        "pressure_delta": pressure_delta,
        "instability_score": instability_score,
        "stability": stability,
        "necessity": necessity,
        "action_type": action_type,
        "acted": acted,
        "timing_window": acted and INTERVENTION_WINDOW_LOW < pressure < INTERVENTION_WINDOW_HIGH,
        "premature_action": acted and pressure < PREMATURE_PRESSURE,
        "late_action": acted and pressure > TOO_LATE_PRESSURE,
    }


__all__ = [
    "HIGH_INSTABILITY_THRESHOLD",
    "INTERVENTION_WINDOW_HIGH",
    "INTERVENTION_WINDOW_LOW",
    "PRESSURE_INCREASE_THRESHOLD",
    "PREMATURE_PRESSURE",
    "SMALL_PRESSURE_THRESHOLD",
    "TOO_LATE_PRESSURE",
    "clamp",
    "evaluate_step_metrics",
    "extract_pressure",
    "extract_instability",
    "get_action_type",
]
