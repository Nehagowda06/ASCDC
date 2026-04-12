# ASCDC API Documentation

## Base URL
```
http://localhost:8000
```

## Auto-Generated Docs
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI JSON**: `http://localhost:8000/openapi.json`

---

## Core Endpoints

### Health Check
```
GET /health
```
**Response**: `{"status": "ok"}`

---

### State Management

#### Get Current State
```
GET /state
```
**Response**:
```json
{
  "timestep": 0,
  "queues": {"A": 0, "B": 0, "C": 0},
  "capacities": {"A": 16, "B": 14, "C": 12},
  "latencies": {"A": 1.2, "B": 1.6, "C": 2.1},
  "latency": 1.2,
  "retry_rate": 0.0,
  "error_rate": 0.0,
  "remaining_budget": 100.0,
  "system_pressure": 0.0,
  "instability_score": 0.0,
  "smoothed_drift": 0.0,
  "pending_actions": [],
  "failure_flags": {"collapsed": false},
  "done": false
}
```

#### Reset Environment
```
POST /reset?task_id=firestorm
```
**Query Parameters**:
- `task_id` (optional): Task to reset to

**Response**: Same as `/state`

---

### Actions

#### Step Environment
```
POST /step
Content-Type: application/json

{
  "type": "scale",
  "target": "A",
  "action_type": "scale"
}
```

**Request Body**:
- `type` (string): Action type (noop, scale, restart, throttle)
- `target` (string): Target queue (A, B, C)
- `action_type` (string): Same as type

**Response**:
```json
{
  "observation": {...},
  "reward": 2.5,
  "done": false,
  "info": {
    "latency": 1.2,
    "stability": 0.8,
    "pressure_delta": -0.1,
    "necessity": true,
    "timing_window": true,
    "counterfactual_impact": 0.5,
    "was_action_necessary": true
  }
}
```

---

### Recommendations

#### Get Recommendation
```
POST /recommend
Content-Type: application/json

{
  "system_pressure": 1.5,
  "queues": {"A": 5, "B": 3, "C": 1}
}
```

**Request Body** (optional): Current state snapshot

**Response**:
```json
{
  "action": {
    "type": "scale",
    "target": "A",
    "action_type": "scale"
  },
  "impact": 0.75,
  "was_necessary": true,
  "confidence": 0.85,
  "explanation": "Queue A pressure exceeds threshold...",
  "evaluated_actions": [
    {
      "action": {"type": "scale", "target": "A"},
      "label": "SCALE A",
      "impact": 0.75,
      "necessary": true
    }
  ],
  "reasoning": {
    "best_action": "SCALE A",
    "confidence": 0.85,
    "impact": 0.75,
    "was_necessary": true,
    "agent_name": "SmartAgent",
    "agent_action": "SCALE A",
    "agent_action_impact": 0.75,
    "agent_action_rank": 1,
    "agent_action_matches_best": true
  }
}
```

---

### Tasks

#### List Tasks
```
GET /tasks
```

**Response**:
```json
{
  "firestorm": {
    "name": "Firestorm",
    "description": "High load spike scenario",
    "config": {...}
  },
  "slow_leak": {
    "name": "Slow Leak",
    "description": "Gradual degradation scenario",
    "config": {...}
  }
}
```

---

### Grading

#### Grade Trajectory
```
POST /grader
Content-Type: application/json

[
  {
    "observation": {...},
    "action": {"type": "scale", "target": "A"},
    "next_observation": {...},
    "info": {...}
  }
]
```

**Request Body**: Array of trajectory steps

**Response**:
```json
{
  "score": 0.75
}
```

---

### Baselines

#### Run Baseline Evaluation
```
POST /baseline
```

**Response**:
```json
{
  "simple-adaptive": {
    "score": 0.65,
    "total_reward": -150.5,
    "steps": 45,
    "collapsed": false
  },
  "strong-decision": {
    "score": 0.82,
    "total_reward": -80.3,
    "steps": 50,
    "collapsed": false
  }
}
```

---

### Agents

#### List Available Agents
```
GET /agents
```

**Response**:
```json
{
  "available": ["simple-adaptive", "strong-decision", "simple-learning"],
  "current": "strong-decision"
}
```

#### Switch Agent
```
POST /agents/{agent_name}
```

**Path Parameters**:
- `agent_name`: Agent to switch to

**Response**:
```json
{
  "message": "Switched to strong-decision",
  "agent": "strong-decision"
}
```

---

### Metrics

#### Get Simple Metrics
```
GET /metrics
```

**Response**:
```json
{
  "total_reward": -120.5,
  "necessary_action_ratio": 0.75,
  "average_impact": 0.45,
  "positive_impact_rate": 0.68
}
```

#### Reset Metrics
```
POST /metrics/reset
```

**Response**:
```json
{
  "message": "Metrics reset"
}
```

---

### Auto Runner

#### Get Auto Status
```
GET /auto/status
```

**Response**:
```json
{
  "running": true,
  "state": {...},
  "last_action": {"type": "scale", "target": "A"}
}
```

#### Start Auto Runner
```
POST /auto/start
Content-Type: application/json

{
  "interval": 0.5,
  "task_id": "firestorm"
}
```

**Request Body**:
- `interval` (float): Seconds between steps
- `task_id` (string, optional): Task to run

**Response**: Same as `/auto/status`

#### Stop Auto Runner
```
POST /auto/stop
```

**Response**: Same as `/auto/status`

---

### Logs

#### Get System Logs
```
GET /logs
```

**Response**:
```json
[
  {
    "timestep": 0,
    "action": "SCALE A",
    "pressure": 1.5,
    "instability": 0.2,
    "counterfactual_impact": 0.5,
    "decision_rationale": "Queue A pressure exceeds threshold"
  }
]
```

---

## Error Responses

### 400 Bad Request
```json
{
  "detail": "Invalid action type"
}
```

### 500 Internal Server Error
```json
{
  "detail": "Recommendation system error - using noop fallback"
}
```

---

## Rate Limiting

No rate limiting currently implemented. For production, add:
```python
from slowapi import Limiter
limiter = Limiter(key_func=get_remote_address)
@app.get("/state")
@limiter.limit("100/minute")
def get_state():
    ...
```

---

## Authentication

Currently no authentication. For production, add:
```python
from fastapi.security import HTTPBearer
security = HTTPBearer()

@app.get("/state")
def get_state(credentials: HTTPAuthCredentials = Depends(security)):
    ...
```

---

## CORS

CORS is enabled for all origins. For production, restrict:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourdomain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## Pagination

Not implemented. For large datasets, add:
```python
@app.get("/logs")
def get_logs(skip: int = 0, limit: int = 100):
    return logs[skip:skip+limit]
```

---

## Versioning

API is currently v1 (implicit). For versioning:
```python
@app.get("/v1/state")
@app.get("/v2/state")
```

---

## Examples

### Python
```python
import requests

# Get state
response = requests.get("http://localhost:8000/state")
state = response.json()

# Step environment
action = {"type": "scale", "target": "A", "action_type": "scale"}
response = requests.post("http://localhost:8000/step", json=action)
result = response.json()

# Get recommendation
response = requests.post("http://localhost:8000/recommend", json=state)
recommendation = response.json()
```

### JavaScript
```javascript
// Get state
const state = await fetch("http://localhost:8000/state").then(r => r.json());

// Step environment
const action = {type: "scale", target: "A", action_type: "scale"};
const result = await fetch("http://localhost:8000/step", {
  method: "POST",
  headers: {"Content-Type": "application/json"},
  body: JSON.stringify(action)
}).then(r => r.json());

// Get recommendation
const recommendation = await fetch("http://localhost:8000/recommend", {
  method: "POST",
  headers: {"Content-Type": "application/json"},
  body: JSON.stringify(state)
}).then(r => r.json());
```

### cURL
```bash
# Get state
curl http://localhost:8000/state

# Step environment
curl -X POST http://localhost:8000/step \
  -H "Content-Type: application/json" \
  -d '{"type":"scale","target":"A","action_type":"scale"}'

# Get recommendation
curl -X POST http://localhost:8000/recommend \
  -H "Content-Type: application/json" \
  -d '{"system_pressure":1.5}'
```

---

## Changelog

### v1.0.0
- Initial API release
- Core endpoints: state, step, recommend, tasks, grader
- Agent management: list, switch
- Auto runner: start, stop, status
- Metrics: get, reset
- Logs: get
