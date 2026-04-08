# ASCDC
Adaptive System Control & Decision Console

A counterfactual decision engine for stabilizing distributed systems under delayed feedback, constrained actions, and non-linear dynamics.

---

## Overview

ASCDC models a stateful, multi-queue distributed system where interventions have **delayed, cascading, and sometimes irreversible effects**.

The system is designed to answer a harder question than standard control:

> Not “what action improves the system?”  
> but “was acting necessary at all?”

It does this through **temporal simulation + counterfactual evaluation**, exposing decision quality under uncertainty.

---

## Key Capabilities

### 1. Delayed & Multi-Step Effects
- Actions are scheduled (not immediate)
- Effects propagate across multiple future timesteps
- Includes secondary consequences (retry spikes, latency impact, instability penalties)

---

### 2. Counterfactual Decision Evaluation
- Every action is evaluated against a **noop baseline**
- Uses multi-step rollout with discounting
- Measures **decision necessity**, not just outcome

---

### 3. Temporal Instability Modeling
- System pressure (utilization + retry + error)
- Exponential instability accumulation (irreversibility)
- Latent drift (slow degradation without visible pressure)
- Recovery dynamics with hysteresis

---

### 4. Constraint-Aware Control
- Budget-limited actions
- Action locks (cooldowns per target)
- Invalid actions rejected with penalties
- Forces tradeoffs and planning

---

### 5. Proactive + Reactive Control
- Agents detect:
  - visible instability (pressure spikes)
  - latent instability (drift)
- Supports early intervention before failure

---

### 6. Multiple Agent Types

- `simple-adaptive`  
  Heuristic baseline

- `strong-decision`  
  Rollout-based planning agent (sequence-aware)

- `simple-learning`  
  State-aware Q-learning with temporal credit assignment

---

### 7. Deterministic & Reproducible

- Seed-controlled environment
- Deterministic rollouts
- Counterfactual fairness guaranteed via cloned state
- No stochastic leakage between evaluation paths

---

### 8. Observability & Debugging

- Full system state exposure (`/state`)
- Structured logs:
  - action
  - pressure
  - instability
  - counterfactual impact
  - decision rationale
- Delayed effect visualization
- Drift + inactivity tracking

---

## System Design Highlights

- **Time is first-class**  
  Decisions must account for delayed consequences

- **Counterfactual correctness**  
  Action vs noop comparison ensures meaningful evaluation

- **No trivial policies**  
  “Always act” and “always wait” both fail

- **Non-linear dynamics**  
  Late actions become ineffective due to instability escalation

---

## Project Structure

env/        → simulation environment (core dynamics)  
core/       → agents, rollout logic, runners  
agents/     → learning + heuristic agents  
grader/     → evaluation logic (aligned with reward)  
server/     → FastAPI backend  
src/        → React frontend  

---

## Running the Project

### Backend

```bash
cd server
python -m venv venv
source venv/bin/activate     # Windows: venv\Scripts\activate

pip install -r requirements.txt
uvicorn app:app --reload
```

Backend:
http://localhost:8000

---

### Frontend

```bash
cd src
npm install
npm run dev
```

Frontend:
http://localhost:5173

---

### Baseline Run (optional)

```bash
python run_baseline.py
```

---

## Usage

- **Dashboard** → system overview + recommendations  
- **Simulation** → manual / auto control  
- **Agents** → switch decision strategies  
- **System Logs** → inspect decisions and counterfactuals  

---

## Evaluation Alignment

- Reward and grader share the same transition metrics  
- Counterfactual rollouts use identical initial states  
- Deterministic execution ensures reproducible scoring  

---

## Summary

ASCDC is not a reactive simulator.

It is a **decision evaluation system** that models:
- delayed causality
- constrained intervention
- temporal risk accumulation
- and counterfactual correctness

to determine when intervention is actually justified.
