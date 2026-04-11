# ASCDC Core Algorithms - Senior Engineer Documentation

## 1. Counterfactual Evaluation (core/counterfactual.py)

### Algorithm: Parallel Rollout Comparison

**Purpose**: Measure decision necessity by comparing action outcome against noop baseline.

**Pseudocode**:
```
evaluate(env, action):
  if env._cf_active:
    return zero_impact()  // Guard: prevent nested counterfactuals
  
  action_reward = simulate(env, action)
  noop_reward = simulate(env, noop)
  
  impact = action_reward - noop_reward
  ratio = impact / max(|noop_reward|, 1.0)
  
  return {
    counterfactual_impact: impact,
    was_action_necessary: impact ≥ 0.75 AND ratio ≥ 0.12,
    had_meaningful_impact: impact ≥ 0.4 AND ratio ≥ 0.06
  }

simulate(env, initial_action):
  env_copy = deepcopy(env)
  preserve_rng_state(env_copy, env)
  
  total_reward = 0
  action = initial_action
  for step in 0..horizon:
    _, reward, done, _ = env_copy.step(action, cf=false)
    total_reward += reward
    if done: break
    action = noop  // Only first action matters
  
  return total_reward
```

**Key Design Decisions**:
- **Deterministic Cloning**: Deep copy + RNG state preservation ensures identical trajectories
- **Single Action Evaluation**: Only first action applied; rest are noops (isolates action effect)
- **Nested Guard**: `_cf_active` flag prevents infinite recursion
- **Thresholds**: Necessity (0.75 impact, 0.12 ratio) prevents trivial policies

**Complexity**: O(horizon) per evaluation

---

## 2. Instability Dynamics (env/environment.py)

### Algorithm: Non-Linear Accumulation with Regime Shifts

**Purpose**: Model irreversible system degradation through exponential instability accumulation.

**Pseudocode**:
```
update_instability(pressure, prev_pressure):
  // Regime shift: high pressure triggers exponential growth
  if pressure > 1.25:
    excess = pressure - 1.25
    instability += excess * 0.45  // Growth rate
  else:
    instability *= 0.82  // Decay in normal conditions
  
  // Reset only on sustained improvement
  if (prev_pressure - pressure) ≥ 0.15:
    instability *= 0.35  // Partial reset
  
  // Exponential escalation: instability → error/retry spike
  escalation = exp(min(instability, 3.0) * 0.4) - 1.0
  retry_rate += 0.12 * escalation + 0.08 * instability
  error_rate += 0.18 * escalation + 0.1 * instability
```

**Key Design Decisions**:
- **Threshold-Based Growth**: Only accumulates when pressure > 1.25 (prevents noise)
- **Exponential Escalation**: Creates regime shifts where late actions become ineffective
- **Partial Reset**: Requires sustained improvement (0.15 pressure drop) to reset
- **Hysteresis**: Asymmetric growth/decay creates path-dependent behavior

**Complexity**: O(1) per step

---

## 3. Grading System (grader/grader.py)

### Algorithm: Multi-Dimensional Trajectory Evaluation

**Purpose**: Assign deterministic score (0-1) to agent trajectories across three dimensions.

**Pseudocode**:
```
grade(trajectory):
  steps = extract_steps(trajectory)
  
  // Compute three independent scores
  stability = evaluate_stability(steps)      // 40% weight
  timing = evaluate_timing(steps)            // 40% weight
  smoothness = evaluate_smoothness(steps)    // 20% weight
  
  score = 0.4*stability + 0.4*timing + 0.2*smoothness
  
  // Collapse penalty: system pressure > 5.0
  if any_step.pressure > 5.0:
    score *= 0.2
  
  return clamp(score, 0, 1)

evaluate_stability(steps):
  avg_latency = mean(step.latency for step in steps)
  avg_pressure = mean(step.pressure for step in steps)
  avg_transition_stability = mean(step.stability for step in steps)
  
  latency_score = 1 - (avg_latency / 10.0)
  pressure_score = 1 - (avg_pressure / 3.0)
  
  return 0.35*latency_score + 0.25*pressure_score + 0.4*avg_transition_stability

evaluate_timing(steps):
  missed = count(step where necessity=true AND action=noop)
  unnecessary = count(step where action≠noop AND necessity=false)
  timely = count(step where action≠noop AND timing_window=true)
  
  missed_penalty = missed / actionable_moments
  unnecessary_penalty = unnecessary / total_actions
  timely_reward = timely / total_actions
  
  return 0.35 + 0.45*timely_reward - 0.35*missed_penalty - 0.25*unnecessary_penalty

evaluate_smoothness(steps):
  // Pressure oscillation: count sign flips in pressure_delta
  pressure_flips = count_sign_changes(step.pressure_delta for step in steps)
  pressure_penalty = pressure_flips / max(1, significant_deltas - 1)
  
  // Action oscillation: count action type changes
  action_flips = count_changes(step.action_type for step in steps if action≠noop)
  action_penalty = action_flips / max(1, action_steps - 1)
  
  return 1 - (0.75*pressure_penalty + 0.25*action_penalty)
```

**Key Design Decisions**:
- **Weighted Combination**: Stability and timing equally important (40% each)
- **Collapse Penalty**: 5x multiplier for system failure (pressure > 5.0)
- **Necessity Detection**: Distinguishes missed vs unnecessary actions
- **Oscillation Penalty**: Penalizes thrashing (frequent action changes)

**Complexity**: O(n) where n = trajectory length

---

## 4. SmartAgent Planning (core/agents/smart_agent.py)

### Algorithm: Horizon-Based Rollout Evaluation

**Purpose**: Select best action by evaluating multi-step sequences through environment simulation.

**Pseudocode**:
```
act(env):
  observation = normalize(env)
  
  // Early exits for trivial cases
  if action_cooldown > 0: return noop
  if total_queues < 0.1: return noop
  if is_stable_state(observation): return noop
  
  // Proactive intervention for drift
  if proactive_action = detect_drift(observation):
    action_cooldown = 2
    return proactive_action
  
  // Evaluate all action sequences
  best_action = null
  best_score = -∞
  noop_score = -∞
  
  for action in possible_actions:
    for followup in [noop, throttle(action.target)]:
      sequence = [action, followup]
      score = evaluate_sequence(env, sequence)
      
      // Penalize action switching
      if action.type ≠ last_action.type:
        score -= 0.15
      
      if action.type = noop:
        noop_score = max(noop_score, score)
      else:
        if score > best_score:
          best_score = score
          best_action = action
  
  // Conservative: prefer noop if action barely better
  if best_score < noop_score + 0.4:
    return noop
  
  action_cooldown = 2
  return best_action

evaluate_sequence(env, actions):
  env_copy = clone(env)
  total_reward = 0
  discount = 1.0
  
  for step in 0..horizon:
    action = actions[step] if step < len(actions) else noop
    _, reward, done, _ = env_copy.step(action, cf=false)
    total_reward += reward * discount
    discount *= 0.85
    if done: break
  
  score = total_reward
  
  // Pressure-based bonuses
  if pressure > 2.0 AND action[0] ≠ noop:
    score += 0.8  // Reward action in crisis
  if pressure < 0.8 AND action[0] ≠ noop:
    score -= 0.3  // Penalize premature action
  
  return score
```

**Key Design Decisions**:
- **2-Step Sequences**: Evaluates action + followup (captures delayed effects)
- **Discount Factor 0.85**: Values immediate rewards more than distant ones
- **Action Switching Penalty**: -0.15 discourages thrashing
- **Conservative Threshold**: Prefers noop unless action significantly better (+0.4)
- **Proactive Mode**: Detects drift early (smoothed_drift > 0.15)

**Complexity**: O(horizon × |actions|²) per decision

---

## 5. LearningAgent Q-Learning (agents/simple_agent.py)

### Algorithm: Adaptive Q-Learning with Pressure-Aware Exploration

**Purpose**: Learn state-action values through temporal difference updates with adaptive parameters.

**Pseudocode**:
```
state_signature(observation):
  pressure_bucket = round(pressure * 2) / 2  // 0.5 granularity
  bottleneck = argmax(queue_levels)
  error_state = "high" if retry > 0.5 OR error > 0.3 else "normal"
  
  return (pressure_bucket, bottleneck, error_state)

act(observation):
  state = state_signature(observation)
  
  // Pressure-aware exploration
  exploration_rate = epsilon
  if pressure > 2.0:
    exploration_rate *= 0.5  // Less exploration in crisis
  elif pressure < 0.5:
    exploration_rate *= 1.2  // More exploration in calm
  
  if random() < exploration_rate:
    return random_action()
  
  // Exploit: select best known action
  known_values = Q_table[state]
  best_action = argmax(known_values)
  return best_action

observe(action, reward, next_observation):
  state = current_state_signature
  next_state = state_signature(next_observation)
  
  // Adaptive learning rate based on reward magnitude
  reward_magnitude = |reward|
  adaptive_alpha = alpha * (1.0 + 0.2 * min(reward_magnitude, 2.0))
  
  // TD update with bootstrapping
  current_value = Q_table[state][action]
  next_best = max(Q_table[next_state].values())
  
  td_target = reward + gamma * next_best
  td_error = td_target - current_value
  
  Q_table[state][action] += adaptive_alpha * td_error
  
  // Decay exploration and learning rate
  epsilon = max(min_epsilon, epsilon * epsilon_decay)
  alpha = max(min_alpha, alpha * alpha_decay)
```

**Key Design Decisions**:
- **Coarse State Representation**: 0.5 pressure granularity + error_state (reduces state space)
- **Adaptive Learning Rate**: Scales with reward magnitude (crisis learning faster)
- **Pressure-Aware Exploration**: Exploits in crisis, explores in calm
- **FIFO State Eviction**: Removes oldest states when Q-table exceeds max_states
- **Decay Schedules**: Both epsilon and alpha decay slowly (0.993, 0.998)

**Complexity**: O(1) per decision, O(|S| × |A|) space

---

## 6. System Pressure Calculation (env/environment.py)

### Algorithm: Multi-Factor Pressure Aggregation

**Purpose**: Compute system pressure from utilization, retry rate, and error rate.

**Pseudocode**:
```
update_pressure():
  // Queue utilization
  utilization = mean(queue[i] / capacity[i] for i in queues)
  
  // Latency update: pressure-dependent
  for queue in queues:
    queue_pressure = queue[i] / capacity[i]
    latency[queue] = base_latency[queue] * (1 + queue_pressure) + latency_spike[queue]
  
  // Retry and error rates: weighted combination
  base_retry = min(2.0, 0.35*retry_rate + 0.65*utilization)
  base_error = min(2.0, 0.35*error_rate + 0.65*utilization)
  
  // Drift accumulation: slow degradation
  if utilization > 0.6:
    drift_score += 0.02 * utilization
  if pressure < 0.5:
    drift_score *= 0.85  // Decay in calm
  
  smoothed_drift = 0.8*smoothed_drift + 0.2*drift_score
  
  // Instability escalation
  escalation = exp(min(instability, 3.0) * 0.4) - 1.0
  base_retry += 0.12*escalation + 0.08*instability
  base_error += 0.18*escalation + 0.1*instability
  
  // Final pressure
  system_pressure = utilization + 0.75*retry_rate + 0.75*error_rate
```

**Key Design Decisions**:
- **Weighted Combination**: Retry/error weighted 0.75 (significant but not dominant)
- **Latency Coupling**: Pressure increases latency (realistic feedback loop)
- **Drift Accumulation**: Slow degradation without visible pressure (models latent issues)
- **Exponential Escalation**: Instability amplifies retry/error rates
- **Smoothing**: Exponential moving average (0.8 weight) prevents noise

**Complexity**: O(|queues|) per step

---

## 7. Reward Function (env/environment.py)

### Algorithm: Multi-Objective Reward Composition

**Purpose**: Assign step reward balancing stability, timing, and efficiency.

**Pseudocode**:
```
compute_reward(action, step_metrics):
  // Base stability bonus
  reward = 3.6
  
  // Penalties for system state
  latency_penalty = mean(latencies)
  queue_pressure = mean(queue[i] / capacity[i])
  
  reward -= 0.8*latency_penalty
  reward -= 1.1*queue_pressure
  reward -= 0.85*retry_rate
  reward -= 0.85*error_rate
  reward -= 0.1*instability_score
  reward -= 0.12*drift_score
  
  // Stability bonus
  reward += 0.3*(stability - 0.5)
  
  // Pressure improvement bonus
  if pressure_delta < 0:
    reward += 0.5
  if pressure_delta ≤ -0.5:
    reward += 1.0
  
  // Action-specific penalties
  if action = restart: reward -= 0.06
  if action = scale: reward -= 0.02
  if action = throttle: reward -= 0.015
  
  // Timing bonuses
  if action ≠ noop:
    if timing_window: reward += 0.8
    elif premature: reward -= 0.35
    elif late: reward -= 0.2
  
  // Noop rewards (strategic waiting)
  if action = noop:
    if stable_system:
      reward += 0.03 * min(noop_streak, 4)
    else:
      reward -= 0.08 * max(1, noop_streak)
  
  // Inaction penalty when needed
  if steps_since_action > 3 AND (pressure > 0.8 OR drift > 0.2):
    reward -= 0.03 * steps_since_action
  
  return reward
```

**Key Design Decisions**:
- **Base Bonus 3.6**: Encourages any action over collapse
- **Asymmetric Penalties**: Queue pressure (1.1) > latency (0.8)
- **Timing Bonuses**: +0.8 for timely, -0.35 for premature
- **Noop Rewards**: Positive in stable states, negative in unstable
- **Inaction Penalty**: Discourages prolonged waiting when needed

**Complexity**: O(1) per step

---

## Summary: Algorithm Interactions

```
┌─────────────────────────────────────────────────────────────┐
│ Agent Decision Loop                                         │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. Observe state → Compute pressure, instability, drift   │
│  2. Select action → SmartAgent evaluates sequences         │
│  3. Execute action → Delayed effects scheduled             │
│  4. Simulate flow → Queue dynamics, pressure update        │
│  5. Evaluate counterfactual → Compare vs noop baseline     │
│  6. Compute reward → Multi-objective composition           │
│  7. Update metrics → Grading system accumulates score      │
│  8. Learn (if LearningAgent) → Q-table update              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Key Invariants**:
- Deterministic: Same seed → identical trajectory
- Irreversible: Instability accumulates exponentially
- Delayed: Actions take 1-3 steps to apply
- Constrained: Budget limits, action locks, queue dependencies
- Fair: Counterfactual evaluation prevents trivial policies

---

## Performance Characteristics

| Algorithm | Complexity | Space | Notes |
|-----------|-----------|-------|-------|
| Counterfactual | O(horizon) | O(env_size) | Cloning cost dominates |
| Instability | O(1) | O(1) | Per-step update |
| Grading | O(n) | O(n) | n = trajectory length |
| SmartAgent | O(h × a²) | O(env_size) | h=horizon, a=actions |
| LearningAgent | O(1) | O(\|S\| × \|A\|) | Q-table size |
| Pressure | O(\|Q\|) | O(1) | \|Q\| = num queues |
| Reward | O(1) | O(1) | Per-step computation |

---

## Tuning Parameters (Critical)

| Parameter | Value | Impact |
|-----------|-------|--------|
| INSTABILITY_GROWTH_RATE | 0.45 | Exponential accumulation speed |
| COUNTERFACTUAL_HORIZON | 7 | Decision necessity window |
| SmartAgent horizon | 12 | Planning depth |
| LearningAgent alpha | 0.4 | Learning speed |
| LearningAgent gamma | 0.95 | Future value weight |
| Pressure threshold | 1.25 | Instability trigger |

Changing these fundamentally alters system behavior and agent performance.
