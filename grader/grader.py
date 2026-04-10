from __future__ import annotations

from typing import Any, Iterable, List, Mapping, Sequence

from core.evaluation_metrics import (
    PRESSURE_INCREASE_THRESHOLD,
    SMALL_PRESSURE_THRESHOLD,
    clamp,
    evaluate_step_metrics,
    extract_pressure,
    get_action_type,
)


class ASCDCGrader:
    def __init__(self) -> None:
        self.max_latency = 10.0
        self.critical_pressure = 3.0
        self.stabilization_horizon = 3

    def grade(self, trajectory: Iterable[Mapping[str, Any]]) -> float:
        """
        Returns score between 0.0 and 1.0
        Deterministic
        """
        steps = list(trajectory)
        if not steps:
            return 0.0

        step_metrics = [
            evaluate_step_metrics(
                step.get("observation"),
                step.get("action"),
                self._next_state(step),
            )
            for step in steps
        ]
        pressures = [float(metrics["next_pressure"]) for metrics in step_metrics]
        latencies = [self._extract_latency(step) for step in steps]

        stability_score = self._stability_score(pressures, latencies, step_metrics)
        timing_score = self._timing_score(step_metrics)
        smoothness_score = self._smoothness_score(steps, step_metrics)

        collapsed = any(
            bool(self._get_nested(step, "info", "failure_flags", "collapsed", default=False))
            for step in steps
        )

        final_score = (
            0.4 * stability_score +
            0.4 * timing_score +
            0.2 * smoothness_score
        )

        if collapsed:
            final_score *= 0.2

        return round(clamp(final_score), 4)

    def _stability_score(
        self,
        pressures: Sequence[float],
        latencies: Sequence[float],
        step_metrics: Sequence[Mapping[str, Any]],
    ) -> float:
        avg_latency = sum(latencies) / len(latencies) if latencies else 0.0
        avg_pressure = sum(pressures) / len(pressures) if pressures else 0.0
        avg_transition_stability = (
            sum(float(metrics["stability"]) for metrics in step_metrics) / len(step_metrics)
            if step_metrics else 0.0
        )

        latency_score = clamp(1.0 - (avg_latency / self.max_latency))
        pressure_score = clamp(1.0 - (avg_pressure / self.critical_pressure))

        return clamp(0.35 * latency_score + 0.25 * pressure_score + 0.4 * avg_transition_stability)

    def _timing_score(self, step_metrics: Sequence[Mapping[str, Any]]) -> float:
        missed_interventions = 0
        unnecessary_actions = 0
        timely_actions = 0
        total_actions = 0
        actionable_moments = 0

        for metrics in step_metrics:
            action_type = str(metrics["action_type"])
            pressure_delta = float(metrics["pressure_delta"])

            if bool(metrics["necessity"]) or pressure_delta > PRESSURE_INCREASE_THRESHOLD:
                actionable_moments += 1
                if action_type == "noop":
                    missed_interventions += 1

            if action_type != "noop":
                total_actions += 1
                if not bool(metrics["necessity"]):
                    unnecessary_actions += 1
                if bool(metrics["timing_window"]) and float(metrics["stability"]) >= 0.55:
                    timely_actions += 1

        missed_penalty = (
            missed_interventions / actionable_moments
            if actionable_moments > 0 else 0.0
        )
        unnecessary_penalty = (
            unnecessary_actions / total_actions
            if total_actions > 0 else 0.0
        )
        timely_reward = (
            timely_actions / total_actions
            if total_actions > 0 else 0.5
        )

        score = 0.35 + 0.45 * timely_reward - 0.35 * missed_penalty - 0.25 * unnecessary_penalty
        return clamp(score)

    def _smoothness_score(
        self,
        steps: Sequence[Mapping[str, Any]],
        step_metrics: Sequence[Mapping[str, Any]],
    ) -> float:
        significant_signs: List[int] = []
        for metrics in step_metrics:
            delta = float(metrics["pressure_delta"])
            if abs(delta) < SMALL_PRESSURE_THRESHOLD:
                continue
            significant_signs.append(1 if delta > 0 else -1)

        sign_flips = sum(
            1
            for previous, current in zip(significant_signs, significant_signs[1:])
            if previous != current
        )
        pressure_oscillation_penalty = (
            sign_flips / max(1, len(significant_signs) - 1)
            if len(significant_signs) > 1 else 0.0
        )

        action_flips = 0
        previous_action = None
        action_steps = 0
        for step in steps:
            label = self._action_label(step.get("action"))
            if label == "NOOP":
                continue
            action_steps += 1
            if previous_action is not None and previous_action != label:
                action_flips += 1
            previous_action = label

        action_oscillation_penalty = (
            action_flips / max(1, action_steps - 1)
            if action_steps > 1 else 0.0
        )

        return clamp(1.0 - (0.75 * pressure_oscillation_penalty + 0.25 * action_oscillation_penalty))

    def _extract_latency(self, step: Mapping[str, Any]) -> float:
        info = step.get("info")
        if isinstance(info, Mapping):
            value = info.get("latency")
            if value is not None:
                return float(value)

        next_observation = step.get("next_observation")
        if isinstance(next_observation, Mapping):
            value = next_observation.get("latency")
            if value is not None:
                return float(value)

        return 0.0

    @staticmethod
    def _get_nested(step: Mapping[str, Any], *keys: str, default: Any = None) -> Any:
        current: Any = step
        for key in keys:
            if not isinstance(current, Mapping):
                return default
            current = current.get(key)
            if current is None:
                return default
        return current

    @staticmethod
    def _get_action_type(action: Any) -> str:
        return get_action_type(action)

    def _action_label(self, action: Any) -> str:
        action_type = self._get_action_type(action)
        if action_type == "noop":
            return "NOOP"

        if isinstance(action, Mapping):
            target = action.get("target")
        else:
            target = getattr(action, "target", None)

        return f"{action_type.upper()} {target}" if target else action_type.upper()

    def _next_state(self, step: Mapping[str, Any]) -> Mapping[str, Any]:
        next_observation = step.get("next_observation")
        info = step.get("info")

        if isinstance(next_observation, Mapping):
            merged_state = dict(next_observation)
            if isinstance(info, Mapping) and "instability_score" in info and "instability_score" not in merged_state:
                merged_state["instability_score"] = info.get("instability_score")
            return merged_state

        if isinstance(info, Mapping):
            return info

        return {
            "system_pressure": extract_pressure(step.get("observation")),
            "instability_score": 0.0,
        }


__all__ = ["ASCDCGrader"]
