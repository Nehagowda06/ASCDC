import asyncio
import math
import logging
import time
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.requests import Request
from fastapi.responses import JSONResponse

from core.counterfactual import CounterfactualEvaluator
from core.auto_runner import AutoRunner
from core.simple_recommendation import SimpleRecommendationSystem
from agents import create_agent, get_available_agents, set_agent, get_current_agent, get_current_agent_name, get_metrics, update_metrics, reset_metrics
from core.pipeline import EvaluationPipeline
from core.models.policy_agent import PolicyAgent
from env.environment import ASCDCEnvironment
from grader.grader import ASCDCGrader
from tasks.definitions import TASKS


logger = logging.getLogger(__name__)

app = FastAPI()
app.title = "ASCDC OpenEnv"
app.description = (
    "Adaptive System Control with Delayed Consequences. "
    "The API exposes a deterministic control environment with delayed effects, "
    "budget constraints, and built-in counterfactual evaluation against noop rollouts."
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={
            "error": str(exc),
            "path": request.url.path
        }
    )

# Initialize environment and simple recommendation system
active_env = ASCDCEnvironment()
recommendation_system = SimpleRecommendationSystem(active_env)
counterfactual_evaluator = CounterfactualEvaluator()
policy_agent: Optional[PolicyAgent] = None

pipeline = EvaluationPipeline(TASKS)
grader = ASCDCGrader()
baseline_results_cache: Optional[Dict[str, Dict[str, float]]] = None
auto_runner: Optional[AutoRunner] = None
auto_runner_task: Optional[asyncio.Task] = None


def _json_safe(value: Any) -> Any:
    encoded = jsonable_encoder(value)

    if encoded is None:
        return ""
    if isinstance(encoded, float):
        return encoded if math.isfinite(encoded) else 0.0
    if isinstance(encoded, list):
        return [_json_safe(item) for item in encoded if item is not None]
    if isinstance(encoded, dict):
        safe_dict: Dict[str, Any] = {}
        for key, item in encoded.items():
            if item is None:
                continue
            safe_dict[key] = _json_safe(item)
        return safe_dict
    return encoded


def _coerce_action_payload(action: Dict[str, Any]) -> Dict[str, Any]:
    action_type = action.get("type", action.get("action_type"))
    if action_type is None:
        raise HTTPException(status_code=400, detail="Missing action type")

    normalized = dict(action)
    normalized["type"] = str(action_type).lower()
    normalized.pop("action_type", None)

    if normalized["type"] not in ["restart", "scale", "throttle", "noop"]:
        raise HTTPException(status_code=400, detail="Invalid action type")

    if normalized["type"] == "noop":
        return {
            "type": "noop",
            "target": None,
        }

    normalized["target"] = normalized.get("target")

    return normalized


def _normalize_agent_action(action: Dict[str, Any]) -> Dict[str, Any]:
    action_type = str(action.get("type", action.get("action_type", "noop"))).lower()
    if action_type == "noop":
        return {"type": "noop", "target": None}

    return {
        "type": action_type,
        "target": action.get("target"),
    }


async def _shutdown_auto_runner() -> None:
    global auto_runner, auto_runner_task

    if auto_runner is not None:
        auto_runner.stop()

    if auto_runner_task is not None:
        try:
            await asyncio.wait_for(asyncio.shield(auto_runner_task), timeout=2.0)
        except asyncio.TimeoutError:
            logger.warning("Timed out while stopping auto runner.")
        except Exception as exc:
            logger.error("Auto runner stopped with error: %s", exc)

    auto_runner = None
    auto_runner_task = None


def _request_auto_runner_stop() -> None:
    if auto_runner is not None:
        auto_runner.stop()


def _auto_status_payload() -> Dict[str, Any]:
    return {
        "running": bool(auto_runner and auto_runner.running),
        "done": bool(auto_runner and auto_runner.done),
        "interval": auto_runner.interval if auto_runner else None,
        "steps_run": auto_runner.steps_run if auto_runner else 0,
        "stop_reason": auto_runner.stop_reason if auto_runner else "idle",
        "agent_name": get_current_agent_name(),
        "last_reward": auto_runner.last_reward if auto_runner else None,
        "last_action": auto_runner.last_action if auto_runner else None,
        "last_info": auto_runner.last_info if auto_runner else {},
        "state": active_env.state(),
    }


def _record_auto_step(
    action: Dict[str, Any],
    pre_observation: Any,
    observation: Any,
    reward: float,
    done: bool,
    info: Dict[str, Any],
) -> None:
    update_metrics(
        reward,
        _normalize_agent_action(action),
        info,
        pre_observation,
        observation,
    )


@app.get("/")
def root():
    return _json_safe({"message": "ASCDC API running"})
@app.post(
    "/reset",
    summary="Reset active environment",
    description="Resets active ASCDC environment and optionally loads one of predefined deterministic task configurations.",
)
def reset(task_id: Optional[str] = None):
    logger.info("[RESET] task_id=%s", task_id)
    _request_auto_runner_stop()

    if task_id and task_id not in TASKS:
        raise HTTPException(status_code=404, detail="Invalid task_id")

    if task_id:
        config = TASKS[task_id]["config"]
    else:
        config = None

    obs = active_env.reset(config=config)
    reset_metrics()  # Reset simple metrics

    return _json_safe(obs)


@app.post(
    "/recommend",
    summary="Recommend the next action",
    description=(
        "Evaluates noop, restart, scale, and throttle across A, B, and C with counterfactual simulation. "
        "The response always includes the chosen action, normalized confidence, a short explanation, "
        "and ranked alternatives with impacts measured against the noop baseline."
    ),
)
def recommend_action(current_state: Optional[Dict[str, Any]] = None):
    try:
        recommendation = recommendation_system.recommend(current_state)
        return _json_safe(recommendation)
    except Exception as e:
        logger.error(f"Recommendation failed: {e}")
        return _json_safe({
            "action": {"type": "noop", "target": None},
            "impact": 0.0,
            "was_necessary": False,
            "confidence": 0.1,
            "explanation": "Recommendation system error - using noop fallback",
            "evaluated_actions": [{
                "action": {"type": "noop", "target": None},
                "label": "NOOP",
                "impact": 0.0,
                "necessary": False
            }],
            "reasoning": {
                "best_action": "NOOP",
                "confidence": 0.1,
                "impact": 0.0,
                "was_necessary": False,
                "alternative_actions": [{
                    "action": {"type": "noop", "target": None},
                    "label": "NOOP",
                    "impact": 0.0,
                    "necessary": False
                }],
                "explanation": "Recommendation system error - using noop fallback",
                "agent_name": get_current_agent_name(),
                "agent_action": "NOOP",
                "agent_action_impact": 0.0,
                "agent_action_rank": 1,
                "agent_action_matches_best": True
            }
        })


@app.get(
    "/model-info",
    summary="Inspect the policy model status",
    description="Returns whether the optional PyTorch policy model is loaded and whether it came from local storage or Hugging Face.",
)
def get_model_info():
    global policy_agent

    local_model_path = Path("artifacts/ascdc-policy-model.pt")
    if policy_agent is None and local_model_path.exists():
        policy_agent = PolicyAgent(model_path=local_model_path)

    if policy_agent is None:
        return {
            "loaded": False,
            "source": "unavailable",
            "repo_id": "ascdc-policy-model",
            "model_path": str(local_model_path),
        }

    return policy_agent.model_info()


@app.post(
    "/step",
    summary="Advance the environment by one action",
    description=(
        "Applies one control action and returns the next observation, reward, done flag, and debug info. "
        "The info payload always includes counterfactual_impact, defined as reward(action rollout) minus "
        "reward(noop rollout) from the same pre-action state over a short fixed horizon, and "
        "was_action_necessary, which is true when a non-noop action improves outcome versus noop."
    ),
)
def step(action: Dict[str, Any]):
    logger.info("[STEP] action=%s", action)
    _request_auto_runner_stop()

    normalized_action = _coerce_action_payload(action)

    try:
        start = time.time()
        pre_observation = active_env.state()
        counterfactual = counterfactual_evaluator.evaluate(active_env, normalized_action)
        obs, reward, done, info = active_env.step(normalized_action)
        info.update(counterfactual)
        
        # Update simple metrics
        update_metrics(reward, normalized_action, info, pre_observation, obs)
        
        duration = time.time() - start
        logger.info("[STEP] took %.4fs", duration)
        return _json_safe({
            "observation": obs,
            "reward": reward,
            "done": done,
            "info": info
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health():
    return _json_safe({"status": "ok"})


@app.get(
    "/determinism/check",
    summary="Check system determinism",
    description="Runs two identical trajectories from the same seed and verifies if they match exactly.",
)
def check_determinism(seed: int = 42, steps: int = 20):
    def run_sim(s, n):
        env = ASCDCEnvironment(seed=s)
        results = []
        obs = env.reset(seed=s)
        for _ in range(n):
            # Simple policy: scale B if queue > 10, else noop
            action = {"type": "scale", "target": "B"} if obs.queues["B"] > 10 else {"type": "noop", "target": None}
            obs, reward, done, info = env.step(action)
            results.append({
                "reward": reward,
                "pressure": info["pressure"],
                "counterfactual": info["counterfactual_impact"]
            })
            if done:
                break
        return results

    run1 = run_sim(seed, steps)
    run2 = run_sim(seed, steps)

    match = run1 == run2

    return _json_safe({
        "ok": match,
        "seed": seed,
        "steps": len(run1),
        "match": match,
        "details": {
            "run1_first_reward": run1[0]["reward"] if run1 else None,
            "run2_first_reward": run2[0]["reward"] if run2 else None,
        }
    })

@app.get("/logs")
def get_logs():
    return _json_safe(active_env.logs)


@app.get(
    "/state",
    summary="Inspect the hidden environment state",
    description="Returns the current internal state snapshot, including locks, history size, and hidden system variables used by the simulator.",
)
def get_state():
    return _json_safe(active_env.state())


@app.get(
    "/tasks",
    summary="List available tasks",
    description="Returns the deterministic scenario catalog used for evaluation, including incident response, capacity planning, and stability preservation tasks.",
)
def get_tasks():
    return _json_safe({
        task_id: {
            "name": task["name"],
            "description": task["description"]
        }
        for task_id, task in TASKS.items()
    })


@app.post(
    "/grader",
    summary="Grade a trajectory",
    description="Scores a trajectory deterministically from 0.0 to 1.0 using stability, precision, efficiency, and collapse penalties.",
)
def grade(trajectory: List[Dict[str, Any]]):
    score = grader.grade(trajectory)

    return _json_safe({"score": score})


@app.post(
    "/baseline",
    summary="Run built-in baselines",
    description="Evaluates the built-in switchable agents across all tasks using deterministic task configurations and grading.",
)
def run_baseline():
    global baseline_results_cache

    try:
        if baseline_results_cache is not None:
            return _json_safe(baseline_results_cache)

        results = {}

        for agent_name in get_available_agents():
            results[agent_name] = {}

            for task_id in TASKS.keys():
                try:
                    agent = create_agent(agent_name)
                    result = pipeline.run_evaluation(task_id, agent)
                    results[agent_name][task_id] = result["score"]
                except Exception as e:
                    logger.error(f"Error evaluating {agent_name} on {task_id}: {e}")
                    results[agent_name][task_id] = 0.0

        baseline_results_cache = results
        return _json_safe(results)
    except Exception as e:
        logger.error(f"Baseline evaluation failed: {e}")
        raise HTTPException(status_code=500, detail=f"Baseline evaluation failed: {str(e)}")


@app.get("/agents")
def get_agents():
    """Get list of available agents."""
    return _json_safe({
        "available": get_available_agents(),
        "current": get_current_agent_name(),
    })


@app.post("/agents/{agent_name}")
def switch_agent(agent_name: str):
    """Switch to a different agent."""
    _request_auto_runner_stop()
    if set_agent(agent_name):
        return _json_safe({
            "message": f"Switched to agent: {agent_name}",
            "agent": agent_name
        })
    else:
        raise HTTPException(status_code=404, detail=f"Agent not found: {agent_name}")


@app.get("/metrics")
def get_simple_metrics():
    """Get current decision metrics."""
    return _json_safe(get_metrics())


@app.post("/metrics/reset")
def reset_simple_metrics():
    """Reset decision metrics."""
    reset_metrics()
    return _json_safe({"message": "Metrics reset"})


@app.post("/auto/start")
async def start_auto(payload: Optional[Dict[str, Any]] = None):
    global auto_runner, auto_runner_task

    payload = payload or {}
    task_id = payload.get("task_id")
    interval = float(payload.get("interval", 0.5) or 0.5)

    if task_id and task_id not in TASKS:
        raise HTTPException(status_code=404, detail="Invalid task_id")
    if interval <= 0:
        raise HTTPException(status_code=400, detail="interval must be greater than 0")

    if auto_runner_task is not None or (auto_runner is not None and auto_runner.running):
        await _shutdown_auto_runner()

    reset_metrics()

    runner = AutoRunner(active_env, get_current_agent(), interval=interval)
    runner.step_callback = _record_auto_step
    runner.evaluation_callback = lambda env, action: counterfactual_evaluator.evaluate(env, action)
    if task_id:
        runner.reset_config = TASKS[task_id]["config"]

    auto_runner = runner

    async def _run_runner() -> None:
        try:
            await runner.run()
        finally:
            pass

    auto_runner_task = asyncio.create_task(_run_runner())
    await asyncio.sleep(0)

    return _json_safe(_auto_status_payload())


@app.post("/auto/stop")
async def stop_auto():
    await _shutdown_auto_runner()
    return _json_safe(_auto_status_payload())


@app.get("/auto/status")
def get_auto_status():
    return _json_safe(_auto_status_payload())
