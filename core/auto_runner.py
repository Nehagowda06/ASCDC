from __future__ import annotations

import asyncio
import inspect
from copy import deepcopy
from typing import Any, Awaitable, Callable, Dict, Optional


class AutoRunner:
    def __init__(self, env: Any, agent: Any, interval: float = 0.5):
        self.env = env
        self.agent = agent
        self.interval = interval
        self.running = False
        self.done = False
        self.steps_run = 0
        self.stop_reason = "idle"
        self.last_reward: Optional[float] = None
        self.last_info: Dict[str, Any] = {}
        self.last_action: Dict[str, Any] | None = None
        self.latest_observation: Any = None
        self.reset_config: Optional[Dict[str, Any]] = None
        self.step_callback: Optional[
            Callable[[Dict[str, Any], Any, float, bool, Dict[str, Any]], Any]
        ] = None
        self.evaluation_callback: Optional[
            Callable[[Any, Dict[str, Any]], Dict[str, Any]]
        ] = None

    async def run(self):
        self.running = True
        self.done = False
        self.steps_run = 0
        self.last_reward = None
        self.last_info = {}
        self.last_action = None
        self.stop_reason = "running"

        if self.reset_config is not None:
            observation = self.env.reset(config=deepcopy(self.reset_config))
        else:
            observation = self.env.reset()

        self.latest_observation = observation

        try:
            while self.running:
                pre_observation = deepcopy(observation)
                snapshot = observation
                action = self.agent.act(self.env) if hasattr(self.agent, "requires_env") else self.agent.act(snapshot)
                self.last_action = self._normalize_action(action)
                extra_info = {}
                if self.evaluation_callback is not None:
                    extra_info = deepcopy(self.evaluation_callback(self.env, deepcopy(self.last_action)))
                observation, reward, done, info = self.env.step(action)
                info.update(extra_info)

                self.latest_observation = observation
                self.last_reward = float(reward)
                self.last_info = deepcopy(info)
                self.steps_run += 1

                if self.step_callback is not None:
                    maybe_result = self.step_callback(
                        deepcopy(self.last_action),
                        pre_observation,
                        observation,
                        float(reward),
                        bool(done),
                        deepcopy(info),
                    )
                    if inspect.isawaitable(maybe_result):
                        await maybe_result

                if done:
                    self.done = True
                    self.running = False
                    self.stop_reason = "done"
                    break

                await asyncio.sleep(self.interval)

            if not self.done and self.stop_reason == "running":
                self.stop_reason = "stopped"
        finally:
            self.running = False

    def stop(self):
        if self.running and self.stop_reason == "running":
            self.stop_reason = "stopped"
        self.running = False

    @staticmethod
    def _normalize_action(action: Any) -> Dict[str, Any]:
        if isinstance(action, dict):
            action_type = str(action.get("type", action.get("action_type", "noop"))).lower()
            return {
                "type": action_type,
                "target": action.get("target"),
            }

        return {
            "type": str(getattr(action, "type", getattr(action, "action_type", "noop"))).lower(),
            "target": getattr(action, "target", None),
        }


__all__ = ["AutoRunner"]
