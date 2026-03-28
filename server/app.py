import logging
import time
from fastapi import FastAPI, HTTPException
from fastapi.requests import Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from typing import Optional, List, Dict, Any

from env.environment import ASCDCEnvironment
from core.pipeline import EvaluationPipeline, NoOpAgent, ThresholdAgent, GreedyAgent
from grader.grader import ASCDCGrader
from tasks.definitions import TASKS


logger = logging.getLogger(__name__)

app = FastAPI(title="ASCDC OpenEnv")

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

pipeline = EvaluationPipeline(TASKS)


@app.get("/")
def root():
    return {"message": "ASCDC API running"}


@app.post("/reset")
def reset(task_id: Optional[str] = None):
    logger.info("[RESET] task_id=%s", task_id)

    if task_id and task_id not in TASKS:
        raise HTTPException(status_code=404, detail="Invalid task_id")

    if task_id:
        config = TASKS[task_id]["config"]
    else:
        config = None

    obs = active_env.reset(config=config)

    return obs


@app.post("/step")
def step(action: Dict[str, Any]):
    logger.info("[STEP] action=%s", action)

    if "type" not in action:
        raise HTTPException(status_code=400, detail="Missing action type")

    if action["type"] not in ["restart", "scale", "throttle", "noop"]:
        raise HTTPException(status_code=400, detail="Invalid action type")

    try:
        start = time.time()
        obs, reward, done, info = active_env.step(action)
        duration = time.time() - start
        logger.info("[STEP] took %.4fs", duration)
        return {
            "observation": obs,
            "reward": reward,
            "done": done,
            "info": info
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/state")
def get_state():
    return active_env.state()


@app.get("/tasks")
def get_tasks():
    return {
        task_id: {
            "name": task["name"],
            "description": task["description"]
        }
        for task_id, task in TASKS.items()
    }


@app.post("/grader")
def grade(trajectory: List[Dict[str, Any]]):
    score = grader.grade(trajectory)

    return {"score": score}


@app.post("/baseline")
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

    return results
