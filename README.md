# ASCDC: Temporal Decision Intelligence for Systems with Delayed Consequences

## One-Line Summary

A control environment that evaluates not just what actions do, but whether they were necessary.

## Problem

Many real-world systems respond with delay. Restarting a service, scaling capacity, or throttling requests may not improve the system immediately, and sometimes the effects appear only after instability has already spread downstream.

This creates a timing problem:

- agents that overreact waste budget and apply unnecessary control actions
- agents that react too late allow queues, retries, and errors to compound

In delayed systems, timing is part of decision quality. Acting early, acting late, and choosing not to act can all lead to very different outcomes.

## What This Environment Does

ASCDC simulates a three-stage service pipeline with queues `A -> B -> C`.

The environment includes:

- delayed interventions
- budget constraints
- action locks
- system pressure
- collapse conditions

The agent must manage a non-linear control problem where actions affect queue growth, latency, retry amplification, and error pressure over time.

## Key Innovation

### Counterfactual Evaluation

Every action is compared to a noop rollout from the same pre-action state.

This comparison is horizon-based and evaluates outcomes over multiple future steps rather than only the immediate transition.

Each step produces:

- `counterfactual_impact`
- `was_action_necessary`

`counterfactual_impact` measures the reward difference between taking the chosen action and taking `noop` instead over a short future horizon.

`was_action_necessary` is `true` when the chosen non-noop action improves the outcome versus the noop rollout.

This matters because it teaches when not to act. ASCDC evaluates intervention quality, restraint, and timing together.

## Action Space

Supported actions:

- `restart`
- `scale`
- `throttle`
- `noop`

Both payload styles are supported:

```json
{
  "action_type": "scale",
  "target": "B",
  "amount": 1.0
}
```

```json
{
  "type": "scale",
  "target": "B",
  "amount": 1.0
}
```

For `noop`, `target` may be `null`.

## Observation Space

Required fields:

- `queues`
- `latencies`
- `retry_rate`
- `error_rate`
- `system_pressure`
- `remaining_budget`
- `timestep`
- `done`

Optional fields may include:

- `capacities`
- `latency`
- `pending_actions`

## Tasks

### Incident Response

Immediate overload centered on service `B`. This task tests fast intervention under pressure.

### Capacity Planning

Slow imbalance builds over time. This task tests whether the agent recognizes subtle drift before it becomes a failure.

### Stability Preservation

A transient spike can resolve without intervention. This task tests whether the agent can avoid unnecessary action.

## Metrics

- `total_reward`
- `necessary_action_ratio`
- `average_counterfactual_impact`
- `positive_impact_rate`

These metrics evaluate decision quality, not just system outcomes.

## How to Run

```bash
docker build -t ascdc .
docker run -p 8000:8000 ascdc
```

The API will be available at `http://localhost:8000`.

## API Endpoints

- `GET /`
  Service status message.
- `POST /reset`
  Reset the active environment, optionally with a task configuration.
- `POST /step`
  Apply one action and receive observation, reward, done, and counterfactual-aware info.
- `GET /state`
  Inspect internal environment state.
- `GET /tasks`
  List available deterministic tasks.
- `POST /grader`
  Score a trajectory deterministically.
- `POST /baseline`
  Run built-in baseline agents across all tasks.
- `GET /health`
  Health check endpoint.

Example API usage:

```bash
curl -X POST "http://localhost:8000/reset?task_id=T1_INCIDENT_RESPONSE"
```

```bash
curl -X POST "http://localhost:8000/step" \
  -H "Content-Type: application/json" \
  -d "{\"action_type\":\"scale\",\"target\":\"B\",\"amount\":1.0}"
```

```bash
curl "http://localhost:8000/state"
```

## Key Insight

ASCDC evaluates not just outcomes, but counterfactual necessity of actions in delayed systems.
