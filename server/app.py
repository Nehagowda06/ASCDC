import math
import logging
import time
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.requests import Request
from fastapi.responses import JSONResponse

from core.counterfactual import CounterfactualEvaluator
from core.simple_recommendation import SimpleRecommendationSystem
from agents import get_available_agents, set_agent, get_current_agent_name, get_metrics, update_metrics, reset_metrics
from core.pipeline import EvaluationPipeline, NoOpAgent, ThresholdAgent, GreedyAgent
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

pipeline = EvaluationPipeline(TASKS)
grader = ASCDCGrader()
baseline_results_cache: Optional[Dict[str, Dict[str, float]]] = None


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
    return _json_safe({
        "loaded": True,
        "source": "simple_agent",
        "agent_name": get_current_agent_name(),
        "strategy": get_current_agent_name().replace("simple-", "", 1),
    })


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

    normalized_action = _coerce_action_payload(action)

    try:
        start = time.time()
        counterfactual = counterfactual_evaluator.evaluate(active_env, normalized_action)
        obs, reward, done, info = active_env.step(normalized_action)
        info.update(counterfactual)
        
        # Update simple metrics
        update_metrics(reward, normalized_action, info)
        
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
    description="Evaluates built-in noop, threshold, and greedy agents across all tasks using deterministic task configurations and grading.",
)
def run_baseline():
    global baseline_results_cache

    try:
        if baseline_results_cache is not None:
            return _json_safe(baseline_results_cache)

        agents = {
            "noop": NoOpAgent(),
            "threshold": ThresholdAgent(),
            "greedy": GreedyAgent()
        }

        results = {}

        for agent_name, agent in agents.items():
            results[agent_name] = {}

            for task_id in TASKS.keys():
                try:
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
