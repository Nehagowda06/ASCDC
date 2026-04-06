from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator


VALID_ACTION_TYPES = {"restart", "scale", "throttle", "noop"}
VALID_TARGETS = {"A", "B", "C"}


class Action(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    action_type: str = Field(validation_alias=AliasChoices("action_type", "type"))
    target: Optional[str] = None
    amount: Optional[float] = Field(
        default=1.0,
        validation_alias=AliasChoices("amount", "magnitude"),
    )

    @field_validator("action_type")
    @classmethod
    def validate_action_type(cls, value: str) -> str:
        normalized = value.lower()
        if normalized not in VALID_ACTION_TYPES:
            raise ValueError(f"action_type must be one of {sorted(VALID_ACTION_TYPES)}")
        return normalized

    @field_validator("target")
    @classmethod
    def validate_target(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return value

        normalized = value.upper()
        if normalized not in VALID_TARGETS:
            raise ValueError(f"target must be one of {sorted(VALID_TARGETS)}")
        return normalized

    @model_validator(mode="after")
    def validate_target_requirement(self) -> "Action":
        if self.action_type != "noop" and self.target is None:
            raise ValueError("target is required for restart, scale, and throttle actions")
        return self


class Observation(BaseModel):
    model_config = ConfigDict(extra="allow")

    queues: Dict[str, float]
    latencies: Dict[str, float]
    retry_rate: float
    error_rate: float
    system_pressure: float
    remaining_budget: float
    timestep: int
    done: bool
    capacities: Dict[str, float] = Field(default_factory=dict)
    latency: float = 0.0
    pending_actions: List[Dict[str, Any]] = Field(default_factory=list)


class State(BaseModel):
    model_config = ConfigDict(extra="allow")

    timestep: int
    remaining_budget: float
    history_length: int
    active_locks: Dict[str, int]
    queues: Dict[str, float] = Field(default_factory=dict)
    capacities: Dict[str, float] = Field(default_factory=dict)
    latencies: Dict[str, float] = Field(default_factory=dict)
    latency: float = 0.0
    retry_rate: float = 0.0
    error_rate: float = 0.0
    system_pressure: float = 0.0
    true_load: Dict[str, float] = Field(default_factory=dict)
    delayed_effect_queue: Dict[int, List[Dict[str, Any]]] = Field(default_factory=dict)
    failure_flags: Dict[str, bool] = Field(default_factory=dict)
    history: List[Dict[str, Any]] = Field(default_factory=list)
    seed: Optional[int] = None
