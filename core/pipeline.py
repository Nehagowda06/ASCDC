from __future__ import annotations

from core.runner import TaskRunner
from grader.grader import ASCDCGrader
from env.environment import ASCDCEnvironment


class NoOpAgent:
    def act(self, obs):
        return {"type": "noop", "target": None}


class ThresholdAgent:
    def __init__(self, threshold=10.0):
        self.threshold = threshold

    def act(self, obs):
        queues = obs["queues"] if isinstance(obs, dict) else obs.queues

        if queues["B"] > self.threshold:
            return {"type": "scale", "target": "B"}

        return {"type": "noop", "target": None}


class GreedyAgent:
    def act(self, obs):
        queues = obs["queues"] if isinstance(obs, dict) else obs.queues

        target = max(queues, key=queues.get)

        return {"type": "scale", "target": target}


class EvaluationPipeline:
    def __init__(self, tasks: dict, seed: int = 42):
        self.tasks = tasks
        self.seed = seed
        self.grader = ASCDCGrader()

    def run_evaluation(self, task_id: str, agent):
        if task_id not in self.tasks:
            raise ValueError(f"Unknown task_id: {task_id}")

        task_data = self.tasks[task_id]
        config = task_data["config"]

        # 1. Create fresh environment (deterministic)
        env = ASCDCEnvironment(seed=self.seed)

        # 2. Run task
        runner = TaskRunner(env)
        trajectory = runner.run_task(config, agent)

        # 3. Grade
        score = self.grader.grade(trajectory)

        # 4. Extract summary metrics
        latencies = [step["info"]["latency"] for step in trajectory]
        pressures = [step["info"]["system_pressure"] for step in trajectory]

        stability = max(0.0, 1.0 - (sum(latencies) / len(latencies)) / 10.0)

        total_actions = sum(
            1 for step in trajectory
            if step["action"]["type"] != "noop"
        )

        precision = 1.0 if total_actions == 0 else 1.0 - (total_actions / len(trajectory))

        initial_budget = trajectory[0]["info"]["remaining_budget"]
        final_budget = trajectory[-1]["info"]["remaining_budget"]

        efficiency = final_budget / initial_budget if initial_budget > 0 else 0.0

        collapsed = any(
            step["info"]["failure_flags"]["collapsed"]
            for step in trajectory
        )

        return {
            "task_id": task_id,
            "score": score,
            "trajectory": trajectory,
            "summary": {
                "stability": round(stability, 4),
                "precision": round(precision, 4),
                "efficiency": round(efficiency, 4),
                "collapsed": collapsed
            }
        }
