# ASCDC Algorithm Quick Reference

## Core Insight
ASCDC combines three innovations:
1. **Delayed Causality**: Actions take 1-3 steps to apply (realistic)
2. **Irreversible Consequences**: Instability accumulates exponentially (non-linear)
3. **Counterfactual Evaluation**: Measures decision necessity, not just outcome (fair)

---

## 1. Counterfactual Evaluation

**What**: Compare action outcome vs noop baseline over 7-step horizon

**Why**: Prevents trivial policies (e.g., always restart) from appearing good

**How**:
- Clone environment deterministically
- Run two parallel simulations: action vs noop
- Measure impact = action_reward - noop_reward
- Threshold: impact ≥ 0.75 AND ratio ≥ 0.12 for "necessary"

**Key Code**: `core/counterfactual.py::evaluate()`

---

## 2. Instability Dynamics

**What**: Non-linear exponential accumulation with regime shifts

**Why**: Models irreversible system degradation (cascading failures)

**How**:
```
if pressure > 1.25:
  instability += (pressure - 1.25) * 0.45  // Exponential growth
else:
  instability *= 0.82  // Decay

if (prev_pressure - pressure) ≥ 0.15:
  instability *= 0.35  // Partial reset only on sustained improvement
```

**Effect**: Late actions become ineffective (exponential escalation)

**Key Code**: `env/environment.py::_update_metrics()`

---

## 3. Grading System

**What**: Deterministic trajectory score (0-1) across three dimensions

**Why**: Evaluate agent quality fairly and reproducibly

**How**:
- Stability (40%): latency + pressure + transition stability
- Timing (40%): missed interventions vs unnecessary actions vs timely actions
- Smoothness (20%): pressure oscillation + action oscillation
- Collapse penalty: ×0.2 if pressure > 5.0

**Key Code**: `grader/grader.py::grade()`

---

## 4. SmartAgent Planning

**What**: Evaluate 2-step action sequences through environment simulation

**Why**: Select best action considering delayed effects

**How**:
```
for action in possible_actions:
  for followup in [noop, throttle]:
    score = simulate_sequence(env, [action, followup], horizon=12)
    score += pressure_bonuses()
    if score > best_score:
      best_action = action
```

**Key**: Only first action matters; rest are noops (isolates effect)

**Key Code**: `core/agents/smart_agent.py::_evaluate_sequence()`

---

## 5. LearningAgent Q-Learning

**What**: Learn state-action values with adaptive parameters

**Why**: Improve decisions through experience

**How**:
```
state = (pressure_bucket_0.5, bottleneck_queue, error_state)
Q[state][action] += adaptive_alpha * (reward + gamma * max(Q[next_state]) - Q[state][action])

adaptive_alpha = alpha * (1.0 + 0.2 * min(|reward|, 2.0))
exploration_rate = epsilon * (0.5 if crisis else 1.2 if calm else 1.0)
```

**Key**: Coarse state representation (0.5 pressure granularity) + pressure-aware exploration

**Key Code**: `agents/simple_agent.py::LearningAgent`

---

## 6. System Pressure

**What**: Multi-factor aggregation of utilization, retry, error

**Why**: Single metric for system health

**How**:
```
utilization = mean(queue[i] / capacity[i])
base_retry = 0.35*retry_rate + 0.65*utilization
base_error = 0.35*error_rate + 0.65*utilization
system_pressure = utilization + 0.75*retry_rate + 0.75*error_rate
```

**Key**: Retry/error weighted 0.75 (significant but not dominant)

**Key Code**: `env/environment.py::_update_metrics()`

---

## 7. Reward Function

**What**: Multi-objective composition balancing stability, timing, efficiency

**Why**: Guide agent learning toward good decisions

**How**:
```
reward = 3.6  // Base bonus
reward -= 0.8*latency - 1.1*queue_pressure - 0.85*retry - 0.85*error
reward += 0.3*(stability - 0.5)
reward += pressure_improvement_bonus()
reward += action_timing_bonus()
reward += noop_strategic_bonus()
```

**Key**: Asymmetric penalties (queue > latency), timing bonuses, strategic noop rewards

**Key Code**: `env/environment.py::_compute_reward()`

---

## Critical Thresholds

| Threshold | Value | Meaning |
|-----------|-------|---------|
| Instability trigger | 1.25 | Pressure above this triggers exponential growth |
| Instability reset | 0.15 | Pressure drop needed to partially reset |
| Necessity threshold | 0.75 impact, 0.12 ratio | Action considered necessary |
| Meaningful impact | 0.4 impact, 0.06 ratio | Action had positive effect |
| Collapse threshold | 5.0 pressure | System failure (×0.2 grade penalty) |
| Stable state | <0.4 pressure, <0.03 drift | No action needed |

---

## Complexity Analysis

| Component | Time | Space | Bottleneck |
|-----------|------|-------|-----------|
| Counterfactual | O(horizon) | O(env) | Environment cloning |
| SmartAgent | O(h × a²) | O(env) | Sequence evaluation |
| LearningAgent | O(1) | O(\|S\| × \|A\|) | Q-table lookup |
| Grading | O(n) | O(n) | Trajectory length |
| Step | O(\|Q\|) | O(1) | Queue count |

**Bottleneck**: Counterfactual evaluation (environment cloning is expensive)

---

## Design Patterns

### 1. Deterministic Cloning
```python
env_copy = deepcopy(env)
preserve_rng_state(env_copy, env)  # Critical for reproducibility
```

### 2. Nested Guard
```python
if getattr(env, "_cf_active", False):
  return zero_impact()  # Prevent infinite recursion
```

### 3. Pressure-Aware Exploration
```python
exploration_rate = epsilon
if pressure > 2.0:
  exploration_rate *= 0.5  # Exploit in crisis
elif pressure < 0.5:
  exploration_rate *= 1.2  # Explore in calm
```

### 4. Adaptive Learning Rate
```python
adaptive_alpha = alpha * (1.0 + 0.2 * min(|reward|, 2.0))
# Crisis learning (large reward) → faster updates
```

### 5. Coarse State Representation
```python
pressure_bucket = round(pressure * 2) / 2  # 0.5 granularity
# Reduces state space, improves generalization
```

---

## Tuning Guide

### To Make System Harder
- Increase INSTABILITY_GROWTH_RATE (0.45 → 0.6)
- Increase action delays (SCALE_DELAY: 3 → 4)
- Decrease INSTABILITY_RESET_DELTA (0.15 → 0.1)

### To Make System Easier
- Decrease INSTABILITY_GROWTH_RATE (0.45 → 0.3)
- Decrease action delays (SCALE_DELAY: 3 → 2)
- Increase INSTABILITY_RESET_DELTA (0.15 → 0.2)

### To Improve Agent Learning
- Increase LearningAgent alpha (0.4 → 0.5)
- Increase SmartAgent horizon (12 → 15)
- Decrease epsilon_decay (0.993 → 0.99)

---

## Common Pitfalls

1. **Nested Counterfactuals**: Forgetting `_cf_active` guard → infinite recursion
2. **RNG State Loss**: Not preserving RNG state → non-deterministic clones
3. **Instability Threshold**: Setting too high → system never accumulates instability
4. **Action Delays**: Too short → removes planning requirement; too long → impossible
5. **Reward Scaling**: Unbalanced penalties → agent ignores important factors

---

## Debugging Checklist

- [ ] Counterfactual impact makes sense (action better than noop?)
- [ ] Instability accumulates when pressure high
- [ ] Instability resets when pressure drops sustained
- [ ] Grading score correlates with trajectory quality
- [ ] SmartAgent evaluates sequences correctly
- [ ] LearningAgent Q-values improve over episodes
- [ ] Pressure calculation includes all factors
- [ ] Reward function balanced across objectives

---

## Performance Targets

| Metric | Target | Notes |
|--------|--------|-------|
| Firestorm final pressure | < 0.5 | Incident resolved |
| Slow Leak final pressure | < 0.4 | Drift prevented |
| Ghost Spike recovery | < 20 steps | Spike handled |
| Grading score | > 0.7 | Good trajectory |
| Necessary action ratio | > 0.6 | Good decisions |
| Positive impact rate | > 0.65 | Effective actions |

---

## Key Insights for Senior Engineers

1. **Delayed Causality is Hard**: Most RL assumes instant effects. Planning through delays is non-trivial.

2. **Irreversibility Matters**: Exponential instability creates regime shifts. Early intervention is critical.

3. **Counterfactual Fairness Works**: Comparing vs noop baseline prevents trivial policies. This is the key innovation.

4. **Determinism is Essential**: Stochastic noise obscures decision quality. Deterministic evaluation enables rigorous research.

5. **Multi-Objective Reward is Tricky**: Balancing stability, timing, efficiency requires careful tuning. Asymmetric penalties are important.

6. **State Representation Matters**: Coarse pressure buckets (0.5 granularity) + error_state dimension enables better generalization than fine-grained states.

7. **Pressure-Aware Exploration Works**: Exploiting in crisis, exploring in calm is more efficient than uniform exploration.

8. **Adaptive Learning Rate Helps**: Scaling with reward magnitude enables crisis learning while maintaining stability.

---

## References

- **Counterfactual Evaluation**: Pearl's causal inference framework
- **Instability Dynamics**: Bifurcation theory, regime shifts
- **Grading System**: Multi-objective optimization
- **Planning**: Model-based RL, Monte Carlo tree search
- **Q-Learning**: Sutton & Barto, temporal difference learning
- **Pressure Calculation**: Queueing theory, Little's law
