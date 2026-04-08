from __future__ import annotations

from copy import deepcopy
from pprint import pformat

from core.counterfactual import compute_counterfactual_metrics
from core.pipeline import ThresholdAgent
from core.runner import TaskRunner
from env.environment import ASCDCEnvironment
from tasks.definitions import TASKS


def main() -> None:
    task_id = "T1_INCIDENT_RESPONSE"
    task_config = deepcopy(TASKS[task_id]["config"])
    seed = int(task_config.get("seed", 42))
    task_config["seed"] = seed

    env = ASCDCEnvironment(seed=seed)
    agent = ThresholdAgent()
    runner = TaskRunner(env)

    trajectory = runner.run_task(task_config, agent)
    total_reward = sum(float(step["reward"]) for step in trajectory)
    average_reward = total_reward / len(trajectory) if trajectory else 0.0
    metrics = compute_counterfactual_metrics(trajectory)
    done = bool(trajectory[-1]["done"]) if trajectory else False
    final_state = env.state()

    print("ASCDC Baseline Evaluation")
    print(f"task_id: {task_id}")
    print(f"seed: {seed}")
    print(f"steps: {len(trajectory)}")
    print()
    print("Final Scores")
    print(f"  total_reward: {total_reward:.4f}")
    print(f"  average_reward: {average_reward:.4f}")
    print(f"  necessary_action_ratio: {metrics['necessary_action_ratio'] * 100:.2f}%")
    print(f"  average_counterfactual_impact: {metrics['average_impact']:.6f}")
    print(f"  positive_impact_rate: {metrics['positive_impact_rate'] * 100:.2f}%")
    print(f"  done: {done}")
    print()
    print("Final State")
    print(pformat(final_state, sort_dicts=True))


if __name__ == "__main__":
    main()
