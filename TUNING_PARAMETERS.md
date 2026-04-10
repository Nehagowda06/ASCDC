# Detailed Tuning Parameters

## Environment Configuration (UNCHANGED)

### Action Delays (env/environment.py)
```python
SCALE_DELAY = 3          # UNCHANGED - planning window required
RESTART_DELAY = 2        # UNCHANGED - consequences unfold
THROTTLE_DELAY = 1       # UNCHANGED - gradual control
```

### Instability Dynamics (env/environment.py)
```python
INSTABILITY_PRESSURE_THRESHOLD = 1.25      # UNCHANGED
INSTABILITY_RESET_DELTA = 0.15             # UNCHANGED
INSTABILITY_GROWTH_RATE = 0.45             # UNCHANGED - exponential, irreversible
```

**Rationale**: These delays and dynamics are core to the system's design. They force agents to:
- Plan ahead (not react immediately)
- Evaluate counterfactuals (understand necessity)
- Manage irreversible consequences (learn from mistakes)

---

## SimpleAgent Thresholds (agents/simple_agent.py)

### Adaptive Strategy
```python
# Restart thresholds
max_ratio >= 1.8 or pressure >= 2.0        # was 2.0 / 2.2

# Scale thresholds
max_ratio >= 0.85 or pressure >= 0.95      # was 0.95 / 1.0

# Throttle thresholds
max_ratio >= 0.55 and (retry >= 0.3 or error >= 0.2)  # was 0.65 / 0.35 / 0.25
max_ratio >= 0.45 and pressure >= 0.7      # NEW
```

### Conservative Strategy
```python
# Restart thresholds
max_ratio >= 2.5 or pressure >= 2.5        # was 3.0 / 2.8

# Scale thresholds
max_ratio >= 1.3 or pressure >= 1.5        # was 1.5 / 1.7

# Throttle thresholds
max_ratio >= 0.9 or pressure >= 1.2        # NEW
```

### Aggressive Strategy
```python
# Restart thresholds
max_ratio >= 2.0 or pressure >= 2.2        # was 2.5 / 2.4

# Scale thresholds
max_ratio >= 0.65 or pressure >= 0.85      # was 0.75 / 0.9

# Throttle thresholds
max_ratio >= 0.3 or pressure >= 0.45       # was 0.35 / 0.5
```

---

## LearningAgent Parameters (agents/simple_agent.py)

### Q-Learning Hyperparameters
```python
alpha = 0.4              # was 0.3 (faster learning)
alpha_decay = 0.998      # was 0.999 (slower decay)
min_alpha = 0.08         # was 0.05 (higher floor)

gamma = 0.95             # was 0.9 (values future more)

epsilon = 0.25           # was 0.2 (more exploration)
epsilon_decay = 0.993    # was 0.995 (slower decay)
min_epsilon = 0.05       # was 0.02 (higher floor)

max_states = 1000        # was 500 (larger state space)
```

### State Representation
```python
# Old: (pressure_rounded_to_0.1, bottleneck_queue)
# New: (pressure_bucket_0.5, bottleneck_queue, error_state)

pressure_bucket = round(pressure * 2) / 2  # 0.5 granularity
error_state = "high" if (retry_rate > 0.5 or error_rate > 0.3) else "normal"
```

### Adaptive Learning Rate
```python
reward_magnitude = abs(reward)
adaptive_alpha = alpha * (1.0 + 0.2 * min(reward_magnitude, 2.0))
```

### Pressure-Aware Exploration
```python
exploration_rate = epsilon
if pressure > 2.0:
    exploration_rate *= 0.5      # Less exploration in crisis
elif pressure < 0.5:
    exploration_rate *= 1.2      # More exploration in calm
```

---

## SmartAgent Parameters (core/agents/smart_agent.py)

### Planning Horizon
```python
horizon = 12             # was 10 (20% longer planning)
discount = 0.85          # UNCHANGED - preserves planning nature
```

### Action Cooldowns
```python
action_cooldown = 2      # UNCHANGED - preserves planning delays
```

### Scoring Bonuses/Penalties
```python
# Crisis bonus
if pressure > 2.0 and action != "noop":
    score += 0.8         # UNCHANGED - reasonable bonus

# Instability penalty
if instability > 0.4 and action == "noop":
    score -= 0.4         # NEW - penalize inaction when instability builds

# Premature action penalty
if pressure < 0.8 and action != "noop":
    score -= 0.3         # UNCHANGED
```

### Proactive Mode Thresholds
```python
# Activate proactive mode
if smoothed_drift > 0.15:        # UNCHANGED
    proactive_mode = True

# Deactivate proactive mode
elif smoothed_drift < 0.05:      # UNCHANGED
    proactive_mode = False
```

### Stable State Thresholds
```python
# Stable if all of:
pressure < 0.4           # UNCHANGED
smoothed_drift < 0.03    # UNCHANGED
all(queue < 0.05)        # UNCHANGED
```

### Queue Persistence
```python
PERSISTENT_QUEUE_THRESHOLD = 4   # UNCHANGED
```

### Proactive Action Conditions
```python
# Throttle for instability without high pressure
if pressure < 1.0 and instability > 0.3:
    return throttle

# Proactive throttle for persistent queue
if (proactive_mode and 
    persistence > THRESHOLD and 
    smoothed_drift > 0.1 and 
    pressure_delta >= 0.0):      # UNCHANGED
    return throttle
```

---

## Rationale for Each Change

### Why Better SimpleAgent Thresholds?
- Original thresholds were too conservative
- Agents waited too long before intervening
- Better thresholds improve decision timing without changing environment
- Still respects delayed causality and planning requirements

### Why Better State Representation?
- Pressure at 0.1 granularity was too fine (500+ states)
- 0.5 granularity is more generalizable (fewer states)
- Error state captures retry/error patterns agents should learn
- Enables learning different strategies for different conditions

### Why Adaptive Learning Rate?
- Large rewards (crisis recovery) should update faster
- Small rewards (fine-tuning) should update slower
- Balances crisis learning with stability
- Respects the planning-heavy nature of the system

### Why Pressure-Aware Exploration?
- In crisis: exploit known good actions (restart, scale)
- In calm: explore to find better strategies
- Reduces random exploration when it matters most
- Maintains planning discipline

### Why Longer Horizon?
- 10 steps wasn't enough to see effects of delayed actions
- 12 steps allows better planning through action delays
- Better evaluation of multi-step sequences
- Respects the delayed causality design

### Why NOT Change Environment?
- Delayed causality is the core challenge
- Irreversible instability forces meaningful decisions
- Counterfactual evaluation requires planning
- Removing these would fundamentally change the system's purpose

---

## Monitoring Metrics

Track these metrics to validate improvements:

```python
# Per-agent metrics
necessary_action_ratio      # Should increase (better decisions)
positive_impact_rate        # Should increase (more effective actions)
average_impact              # Should increase (stronger effects)
total_reward                # Should increase (better performance)

# System metrics
final_pressure              # Should be < 0.5 for Firestorm
instability_score           # Should be < 0.2 at end
stability_score             # Should be > 0.7
steps_to_stability          # Should be < 40 for Firestorm
```

---

## Tuning Philosophy

1. **Preserve Core Design**: Keep delayed causality and irreversible consequences
2. **Improve Decision-Making**: Better thresholds and state representation
3. **Enable Learning**: Adaptive parameters and pressure-aware exploration
4. **Respect Planning**: Longer horizon but still planning-heavy
5. **Maintain Challenge**: System should still be hard, agents should be smarter
