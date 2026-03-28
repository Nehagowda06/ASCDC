from __future__ import annotations

from typing import Any, Iterable, Mapping


class ASCDCGrader:
    def __init__(self) -> None:
        self.max_latency = 10.0
        self.critical_pressure = 3.0

    def grade(self, trajectory: Iterable[Mapping[str, Any]]) -> float:
        """
        Returns score between 0.0 and 1.0
        Deterministic
        """

        steps = list(trajectory)
        if not steps:
            return 0.0

        total_steps = len(steps)

        # -------------------------------
        # 1. STABILITY SCORE
        # -------------------------------
        latencies = [step["info"]["latency"] for step in steps]
        avg_latency = sum(latencies) / total_steps

        stability_score = max(0.0, 1.0 - (avg_latency / self.max_latency))

        # -------------------------------
        # 2. PRECISION SCORE
        # -------------------------------
        total_actions = 0
        overreactions = 0
        successful_actions = 0

        for step in steps:
            action = step["action"]
            info = step["info"]

            if self._get_action_type(action) == "noop":
                continue

            total_actions += 1

            pressure_delta = info.get("pressure_delta", 0.0)
            system_pressure = info.get("system_pressure", 0.0)

            # Overreaction: acting when system is stable or improving
            if pressure_delta <= 0 and system_pressure < 0.8:
                overreactions += 1

            # Causal success: check scheduled timestep effect
            scheduled_t = info.get("scheduled_timestep")

            if scheduled_t is not None:
                # find matching future step
                for future_step in steps:
                    if future_step["timestep"] == scheduled_t:
                        future_pressure = future_step["info"]["system_pressure"]

                        if future_pressure < system_pressure:
                            successful_actions += 1
                        break

        if total_actions == 0:
            precision_score = 1.0  # good if no unnecessary actions
        else:
            success_rate = successful_actions / total_actions
            overreaction_penalty = overreactions / total_actions

            precision_score = max(0.0, success_rate * (1.0 - overreaction_penalty))

        # -------------------------------
        # 3. EFFICIENCY SCORE
        # -------------------------------
        initial_budget = steps[0]["info"]["remaining_budget"]
        final_budget = steps[-1]["info"]["remaining_budget"]

        if initial_budget > 0:
            efficiency_score = final_budget / initial_budget
        else:
            efficiency_score = 0.0

        efficiency_score = max(0.0, min(1.0, efficiency_score))

        # -------------------------------
        # 4. CATASTROPHE MULTIPLIER
        # -------------------------------
        collapsed = any(step["info"]["failure_flags"]["collapsed"] for step in steps)

        multiplier = 0.1 if collapsed else 1.0

        # -------------------------------
        # FINAL SCORE
        # -------------------------------
        final_score = (
            0.5 * stability_score +
            0.3 * precision_score +
            0.2 * efficiency_score
        ) * multiplier

        return round(max(0.0, min(1.0, final_score)), 4)

    @staticmethod
    def _get_action_type(action: Any) -> str:
        if isinstance(action, Mapping):
            return str(action.get("type", "noop"))
        return str(getattr(action, "type", "noop"))


__all__ = ["ASCDCGrader"]
