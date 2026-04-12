"""
inference.py — ASCDC Hackathon Submission
Scaler School of Technology × Meta × PyTorch × Hugging Face

Rules compliance:
  - Uses OpenAI client for all LLM calls (API_BASE_URL / MODEL_NAME / HF_TOKEN)
  - Emits [START], [STEP], [END] structured stdout logs
  - Runs all 3 deterministic tasks and reports per-task scores
  - No env modification, no external deps beyond requirements.txt
  - Runtime well under 20 min on vcpu=2 / 8 GB RAM
"""

from __future__ import annotations

import json
import os
import sys
from copy import deepcopy
from typing import Any, Dict, List

from openai import OpenAI

from env.environment import ASCDCEnvironment
from core.agents.smart_agent import SmartAgent
from core.counterfactual import CounterfactualEvaluator
from grader.grader import ASCDCGrader
from tasks.definitions import TASKS

# ── ENV VARS (hackathon mandatory) ──────────────────────────────────────────
API_BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
MODEL_NAME   = os.getenv("MODEL_NAME",   "gpt-4o-mini")
HF_TOKEN     = os.getenv("HF_TOKEN",     "no-token")
LLM_DISABLED = API_BASE_URL.rstrip("/") == "http://localhost:8000"
LLM_WARNING_EMITTED = False

client = OpenAI(
    base_url=API_BASE_URL,
    api_key=HF_TOKEN,
    max_retries=0,
)

grader    = ASCDCGrader()
evaluator = CounterfactualEvaluator()


# ── LLM HELPER ───────────────────────────────────────────────────────────────

def llm_decide(obs_summary: str, candidates: List[str]) -> str:
    """
    Ask the LLM to pick the best action from a ranked candidate list.
    Returns the action string chosen by the model (or candidates[0] on failure).
    """
    system_prompt = (
        "You are an expert distributed-systems control agent for the ASCDC environment. "
        "You receive a summary of the current system state and a ranked list of candidate "
        "actions (best first, by counterfactual impact). "
        "Reply with ONLY the action string exactly as given — no explanation."
    )
    user_prompt = (
        f"System state:\n{obs_summary}\n\n"
        f"Candidate actions (ranked best→worst by counterfactual impact):\n"
        + "\n".join(f"  {i+1}. {a}" for i, a in enumerate(candidates))
        + "\n\nChoose the single best action:"
    )
    global LLM_WARNING_EMITTED
    if LLM_DISABLED:
        if not LLM_WARNING_EMITTED:
            print("[LLM WARNING] Falling back to heuristic: API_BASE_URL points to the environment server, not an OpenAI-compatible chat endpoint.")
            LLM_WARNING_EMITTED = True
        return candidates[0]

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            max_tokens=20,
            temperature=0.0,
            timeout=5.0,
        )
        choice = response.choices[0].message.content.strip()
        # Validate the LLM returned one of the candidates
        if choice in candidates:
            return choice
        # Fuzzy match: accept if the candidate string starts with the reply
        for c in candidates:
            if c.startswith(choice) or choice.startswith(c.split()[0]):
                return c
    except Exception as e:
        print(f"[LLM WARNING] Falling back to heuristic: {e}")
        return candidates[0]
    return candidates[0]


def _action_label(action: Dict[str, Any]) -> str:
    t = action.get("type", "noop")
    tgt = action.get("target")
    return f"{t.upper()} {tgt}" if tgt else t.upper()


def _obs_summary(env: ASCDCEnvironment) -> str:
    s = env.state()
    queues = s.get("queues", {})
    caps   = s.get("capacities", {})
    ratios = {
        q: round(queues.get(q, 0.0) / max(caps.get(q, 1.0), 1.0), 3)
        for q in ("A", "B", "C")
    }
    return (
        f"pressure={s.get('system_pressure', 0):.3f}  "
        f"instability={s.get('instability_score', 0):.3f}  "
        f"drift={s.get('smoothed_drift', 0):.3f}  "
        f"budget={s.get('remaining_budget', 0):.1f}  "
        f"queues={queues}  ratios={ratios}  "
        f"retry={s.get('retry_rate', 0):.3f}  "
        f"error={s.get('error_rate', 0):.3f}  "
        f"locks={s.get('active_locks', {})}"
    )


# ── CORE EPISODE RUNNER ──────────────────────────────────────────────────────

def run_task(task_id: str, task_cfg: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run one full episode for a task.
    Uses SmartAgent to generate action decisions,
    then asks the LLM to confirm / override the top pick.
    Returns the graded trajectory summary.
    """
    env   = ASCDCEnvironment(seed=task_cfg.get("seed", 42))
    agent = SmartAgent(horizon=12)
    obs   = env.reset(config=deepcopy(task_cfg))

    trajectory: List[Dict[str, Any]] = []
    step_idx = 0
    max_steps = task_cfg.get("max_timesteps", 100)

    while step_idx < max_steps:
        # 1. Agent generates action via planning
        snapshot  = env._build_observation()
        action    = agent.act(env) if hasattr(agent, "requires_env") else agent.act(snapshot)

        # 2. Score action via counterfactual evaluation
        try:
            cf    = evaluator.evaluate(env, action)
            score = float(cf.get("counterfactual_impact", 0.0))
        except Exception as e:
            print(f"[ERROR] {e}")
            score = 0.0
        
        # Build candidates for LLM (current action + alternatives)
        candidates_raw = [
            action,
            {"type": "noop", "target": None},
            {"type": "scale", "target": "A"},
            {"type": "restart", "target": "B"},
        ]
        
        # 2. Score each candidate so we can rank for the LLM
        scored: List[tuple[float, Dict[str, Any]]] = []
        for cand in candidates_raw:
            try:
                cf    = evaluator.evaluate(env, cand)
                score = float(cf.get("counterfactual_impact", 0.0))
            except Exception as e:
                print(f"[ERROR] {e}")
                score = 0.0
            scored.append((score, cand))
        scored.sort(key=lambda x: x[0], reverse=True)

        ranked_labels = [_action_label(c) for _, c in scored]
        label_to_action = {_action_label(c): c for _, c in scored}

        # 3. Ask LLM to confirm best action (uses OpenAI client — hackathon rule)
        obs_text    = _obs_summary(env)
        chosen_label = llm_decide(obs_text, ranked_labels)
        action       = label_to_action.get(chosen_label, scored[0][1])

        # 4. Step the environment
        cf_info                  = evaluator.evaluate(env, action)
        next_obs, reward, done, info = env.step(action)
        info.update(cf_info)

        trajectory.append({
            "timestep":         env.timestep,
            "observation":      obs,
            "action":           action,
            "reward":           reward,
            "next_observation": next_obs,
            "done":             done,
            "info":             info,
        })

        # ── Mandatory [STEP] log format ──────────────────────────────────
        print(
            f"[STEP] task={task_id} step={step_idx} "
            f"action={_action_label(action)} "
            f"reward={reward:.4f} "
            f"cf_impact={info.get('counterfactual_impact', 0.0):.4f} "
            f"pressure={info.get('system_pressure', 0.0):.3f} "
            f"budget={info.get('remaining_budget', 0.0):.1f} "
            f"necessary={info.get('was_action_necessary', False)}"
        )
        sys.stdout.flush()

        obs = next_obs
        step_idx += 1

        if done:
            break

    score = grader.grade(trajectory)
    total_reward = sum(float(s["reward"]) for s in trajectory)

    return {
        "task_id":      task_id,
        "score":        score,
        "total_reward": round(total_reward, 4),
        "steps":        len(trajectory),
        "collapsed":    any(
            s["info"].get("failure_flags", {}).get("collapsed", False)
            for s in trajectory
        ),
    }


# ── MAIN ─────────────────────────────────────────────────────────────────────

def run() -> None:
    print("[START]")
    sys.stdout.flush()

    all_results: List[Dict[str, Any]] = []

    for task_id, task_data in TASKS.items():
        cfg = deepcopy(task_data["config"])
        print(
            f"[STEP] task={task_id} name={task_data['name']} status=starting"
        )
        sys.stdout.flush()

        result = run_task(task_id, cfg)
        all_results.append(result)

        print(
            f"[STEP] task={task_id} status=complete "
            f"score={result['score']:.4f} "
            f"total_reward={result['total_reward']:.4f} "
            f"steps={result['steps']} "
            f"collapsed={result['collapsed']}"
        )
        sys.stdout.flush()

    # Aggregate
    avg_score  = sum(r["score"]        for r in all_results) / len(all_results)
    avg_reward = sum(r["total_reward"] for r in all_results) / len(all_results)

    print(
        f"[END] tasks={len(all_results)} "
        f"avg_score={avg_score:.4f} "
        f"avg_reward={avg_reward:.4f} "
        f"scores={json.dumps({r['task_id']: r['score'] for r in all_results})}"
    )
    sys.stdout.flush()


if __name__ == "__main__":
    run()
