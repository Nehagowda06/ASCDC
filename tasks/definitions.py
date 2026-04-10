from __future__ import annotations

from copy import deepcopy
import inspect
from typing import Any, Dict, Mapping

from env.environment import ASCDCEnvironment


QUEUE_ORDER = ("A", "B", "C")
REQUIRED_CONFIG_KEYS = (
    "seed",
    "base_load",
    "capacities",
    "initial_queues",
    "initial_budget",
    "max_timesteps",
)
ENVIRONMENT_CONFIG_KEYS = frozenset(
    name
    for name in inspect.signature(ASCDCEnvironment.__init__).parameters
    if name != "self"
)


TASKS: Dict[str, Dict[str, Any]] = {
    "T1_INCIDENT_RESPONSE": {
        "name": "Firestorm",
        "description": "Obvious live incident: an immediate overload that demands fast intervention before the whole pipeline collapses.",
        "config": {
            "seed": 42,
            "base_load": {
                "A": 30.0,
                "B": 5.0,
                "C": 2.0,
            },
            "capacities": {
                "A": 20.0,
                "B": 10.0,
                "C": 10.0,
            },
            "initial_queues": {
                "A": 5.0,
                "B": 8.0,
                "C": 2.0,
            },
            "initial_budget": 100.0,
            "max_timesteps": 50,
        },
    },
    "T2_CAPACITY_PLANNING": {
        "name": "Slow Leak",
        "description": "Quiet but production-critical drift: a mild imbalance compounds into cascading queues and retries if ignored for too long.",
        "config": {
            "seed": 43,
            "base_load": {
                "A": 10.8,
                "B": 2.2,
                "C": 1.2,
            },
            "capacities": {
                "A": 10.0,
                "B": 10.0,
                "C": 10.0,
            },
            "initial_queues": {
                "A": 2.5,
                "B": 0.0,
                "C": 0.0,
            },
            "initial_budget": 50.0,
            "max_timesteps": 80,
            "load_schedule": {
                0: {"A": 10.9},
                1: {"A": 11.1},
                2: {"A": 11.4},
                3: {"A": 11.8},
                4: {"A": 12.2},
                5: {"A": 12.6},
                6: {"A": 13.0},
            },
        },
    },
    "T3_STABILITY_PRESERVATION": {
        "name": "Ghost Spike",
        "description": "Short-lived but dangerous surge: the raw load subsides, but overreacting at the wrong time can amplify downstream damage.",
        "config": {
            "seed": 44,
            "base_load": {
                "A": 9.5,
                "B": 2.0,
                "C": 1.0,
            },
            "capacities": {
                "A": 18.0,
                "B": 20.0,
                "C": 20.0,
            },
            "initial_queues": {
                "A": 4.0,
                "B": 1.5,
                "C": 0.5,
            },
            "initial_budget": 60.0,
            "max_timesteps": 50,
            "load_schedule": {
                0: {"A": 46.0},
                1: {"A": 34.0},
                2: {"A": 20.0},
                3: {"A": 11.0},
            },
        },
    },
}


def get_task(task_id: str) -> Dict[str, Any]:
    if task_id not in TASKS:
        raise KeyError(f"Unknown task '{task_id}'.")
    return deepcopy(TASKS[task_id])


def get_environment_config(task_id: str) -> Dict[str, Any]:
    config = get_task(task_id)["config"]
    return {
        key: deepcopy(value)
        for key, value in config.items()
        if key in ENVIRONMENT_CONFIG_KEYS
    }


def get_initial_queues(task_id: str) -> Dict[str, float]:
    config = get_task(task_id)["config"]
    return deepcopy(config["initial_queues"])


def get_load_schedule(task_id: str) -> Dict[int, Dict[str, float]]:
    config = get_task(task_id)["config"]
    return deepcopy(config.get("load_schedule", {}))


def _validate_queue_mapping(name: str, mapping: Mapping[str, Any]) -> None:
    missing = [queue for queue in QUEUE_ORDER if queue not in mapping]
    if missing:
        raise ValueError(f"{name} is missing queue keys: {', '.join(missing)}")

    extra = [queue for queue in mapping if queue not in QUEUE_ORDER]
    if extra:
        raise ValueError(f"{name} has unsupported queue keys: {', '.join(extra)}")

    for queue in QUEUE_ORDER:
        value = mapping[queue]
        if not isinstance(value, (int, float)):
            raise ValueError(f"{name}[{queue}] must be numeric.")


def _validate_task_definitions() -> None:
    for task_id, task in TASKS.items():
        if "name" not in task or "description" not in task or "config" not in task:
            raise ValueError(f"{task_id} must define name, description, and config.")

        config = task["config"]
        missing_keys = [key for key in REQUIRED_CONFIG_KEYS if key not in config]
        if missing_keys:
            raise ValueError(f"{task_id} is missing required config keys: {', '.join(missing_keys)}")

        _validate_queue_mapping(f"{task_id}.base_load", config["base_load"])
        _validate_queue_mapping(f"{task_id}.capacities", config["capacities"])
        _validate_queue_mapping(f"{task_id}.initial_queues", config["initial_queues"])

        if "load_schedule" in config:
            schedule = config["load_schedule"]
            if not isinstance(schedule, Mapping):
                raise ValueError(f"{task_id}.load_schedule must be a mapping.")
            for timestep, override in schedule.items():
                if not isinstance(timestep, int) or timestep < 0:
                    raise ValueError(f"{task_id}.load_schedule keys must be non-negative integers.")
                if not isinstance(override, Mapping):
                    raise ValueError(f"{task_id}.load_schedule[{timestep}] must be a mapping.")
                for queue, value in override.items():
                    if queue not in QUEUE_ORDER:
                        raise ValueError(
                            f"{task_id}.load_schedule[{timestep}] has unsupported queue '{queue}'."
                        )
                    if not isinstance(value, (int, float)):
                        raise ValueError(
                            f"{task_id}.load_schedule[{timestep}][{queue}] must be numeric."
                        )


_validate_task_definitions()


__all__ = [
    "TASKS",
    "ENVIRONMENT_CONFIG_KEYS",
    "QUEUE_ORDER",
    "get_environment_config",
    "get_initial_queues",
    "get_load_schedule",
    "get_task",
]
