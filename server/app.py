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
from core.operator_agent import OperatorAgent
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
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173"
    ],
    allow_credentials=True,
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

# Single environment instance (stateless enough for validation)
active_env = ASCDCEnvironment(seed=42)

grader = ASCDCGrader()
counterfactual_evaluator = CounterfactualEvaluator()
operator_agent = OperatorAgent(active_env)

pipeline = EvaluationPipeline(TASKS)


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
    summary="Reset the active environment",
    description="Resets the active ASCDC environment and optionally loads one of the predefined deterministic task configurations.",
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
    operator_agent.history.clear()

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
    observation = current_state if current_state else active_env.state().model_dump()
    recommendation = operator_agent.act(observation)
    return _json_safe(recommendation)


@app.get(
    "/model-info",
    summary="Inspect the policy model status",
    description="Returns whether the optional PyTorch policy model is loaded and whether it came from local storage or Hugging Face.",
)
def get_model_info():
    return _json_safe(operator_agent.model_info())


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
    description="Evaluates the built-in noop, threshold, and greedy agents across all tasks using deterministic task configurations and grading.",
)
def run_baseline():
    agents = {
        "noop": NoOpAgent(),
        "threshold": ThresholdAgent(),
        "greedy": GreedyAgent()
    }

    results = {}

    for agent_name, agent in agents.items():
        results[agent_name] = {}

        for task_id in TASKS.keys():
            result = pipeline.run_evaluation(task_id, agent)
            results[agent_name][task_id] = result["score"]

    return _json_safe(results)
