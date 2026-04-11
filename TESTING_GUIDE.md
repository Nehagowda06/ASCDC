# Testing Guide for Tuned Agents

## Quick Test Scenarios

### 1. Firestorm (T1_INCIDENT_RESPONSE) - Critical Test
**Expected**: System should stabilize within 30-40 steps

```bash
# Test with strong-decision agent
Agent: strong-decision
Task: T1_INCIDENT_RESPONSE (Firestorm)
Expected Outcome:
  - Pressure drops from ~3.0 to < 0.5 by step 30
  - Instability score < 0.2 at end
  - Stability score > 0.7
  - Total reward > 50
```

**What to look for:**
- ✅ Immediate restart of Queue A (crisis mode)
- ✅ Pressure drops quickly (faster delays working)
- ✅ Instability doesn't spike uncontrollably
- ✅ System reaches stable state

### 2. Slow Leak (T2_CAPACITY_PLANNING) - Learning Test
**Expected**: Learning agent should learn to throttle early

```bash
# Test with simple-learning agent
Agent: simple-learning
Task: T2_CAPACITY_PLANNING (Slow Leak)
Expected Outcome:
  - Learns to throttle Queue A around step 10-15
  - Pressure stays < 1.5 throughout
  - Fewer necessary actions (better timing)
  - Positive impact rate > 0.6
```

**What to look for:**
- ✅ Agent learns pattern of Queue A buildup
- ✅ Proactive throttling prevents cascade
- ✅ Fewer total actions needed
- ✅ Better necessary_action_ratio

### 3. Ghost Spike (T3_STABILITY_PRESERVATION) - Stability Test
**Expected**: All agents handle sudden spike gracefully

```bash
Agent: strong-decision
Task: T3_STABILITY_PRESERVATION (Ghost Spike)
Expected Outcome:
  - Handles spike without collapse
  - Quick recovery to stable state
  - Minimal instability accumulation
```

---

## Comparative Testing

### Before vs After Metrics

Run each agent on each task and compare:

```
Metric                  Before    After     Target
─────────────────────────────────────────────────
Firestorm (strong-decision):
  Final Pressure        > 1.5     < 0.5     ✓
  Instability Score     > 0.5     < 0.2     ✓
  Stability Score       < 0.5     > 0.7     ✓
  Total Reward          < 50      > 50      ✓

Slow Leak (simple-learning):
  Necessary Ratio       < 0.4     > 0.6     ✓
  Positive Impact Rate  < 0.5     > 0.65    ✓
  Total Actions         > 15      < 12      ✓

Slow Leak (simple-adaptive):
  Final Pressure        > 1.0     < 0.4     ✓
  Steps to Stability    > 50      < 35      ✓
```

---

## Agent-by-Agent Testing

### SimpleAgent (Adaptive)
```
Test: Firestorm
Expected: Pressure drops to ~1.0-1.5 by end
Reason: More aggressive thresholds

Test: Slow Leak
Expected: Proactive throttling prevents buildup
Reason: Lower throttle threshold (0.45 vs 0.65)

Test: Ghost Spike
Expected: Handles spike, recovers quickly
Reason: Aggressive restart at 1.8 ratio
```

### SimpleAgent (Conservative)
```
Test: Firestorm
Expected: Slower response, pressure stays high
Reason: Still conservative, but better than before

Test: Slow Leak
Expected: Minimal intervention, stable
Reason: Only acts when necessary

Test: Ghost Spike
Expected: Delayed response, but recovers
Reason: Waits for clear crisis signal
```

### SimpleAgent (Aggressive)
```
Test: Firestorm
Expected: Rapid intervention, good recovery
Reason: Most aggressive thresholds

Test: Slow Leak
Expected: Over-intervention, but stable
Reason: Acts on any imbalance

Test: Ghost Spike
Expected: Immediate response, quick recovery
Reason: Aggressive restart at 2.0 ratio
```

### LearningAgent
```
Test: Firestorm (first run)
Expected: Struggles initially, learns crisis pattern
Reason: Needs exploration to find good actions

Test: Firestorm (subsequent runs)
Expected: Improves with each episode
Reason: Q-table learns crisis responses

Test: Slow Leak (multiple episodes)
Expected: Learns to throttle early
Reason: Consistent pattern allows learning

Metrics to track:
  - Episode 1: necessary_ratio ~0.3
  - Episode 5: necessary_ratio ~0.5
  - Episode 10: necessary_ratio ~0.65
```

### SmartAgent (Strong-Decision)
```
Test: Firestorm
Expected: Immediate restart, quick stabilization
Reason: Crisis mode + longer horizon

Test: Slow Leak
Expected: Proactive throttling, minimal actions
Reason: Better lookahead and proactive mode

Test: Ghost Spike
Expected: Handles spike, recovers quickly
Reason: Crisis detection + planning

Metrics to track:
  - Pressure drops within 5 steps
  - Instability < 0.3 by step 20
  - Stability > 0.7 at end
```

---

## Debugging Checklist

If agents don't perform as expected:

### Check 1: Environment Changes Applied
```python
# Verify in env/environment.py
assert SCALE_DELAY == 1
assert RESTART_DELAY == 1
assert THROTTLE_DELAY == 0
assert INSTABILITY_GROWTH_RATE == 0.35
```

### Check 2: SimpleAgent Thresholds
```python
# Verify in agents/simple_agent.py
# Adaptive strategy should have:
# - Restart at 1.8 ratio
# - Scale at 0.85 ratio
# - Throttle at 0.55 ratio + error condition
```

### Check 3: LearningAgent Parameters
```python
# Verify in agents/simple_agent.py
assert alpha == 0.4
assert gamma == 0.95
assert epsilon == 0.25
assert max_states == 1000
```

### Check 4: SmartAgent Crisis Mode
```python
# Verify in core/agents/smart_agent.py
# Should have _crisis_intervention() method
# Should have _update_crisis_mode() method
# Horizon should be 15
```

### Check 5: State Representation
```python
# LearningAgent state should be 3-tuple:
# (pressure_bucket, bottleneck_queue, error_state)
# Not 2-tuple: (pressure, bottleneck)
```

---

## Performance Expectations

### Firestorm Scenario
| Agent | Before | After | Improvement |
|-------|--------|-------|-------------|
| simple-adaptive | Pressure ~2.0 | Pressure ~0.8 | 60% ↓ |
| simple-conservative | Pressure ~2.5 | Pressure ~1.2 | 52% ↓ |
| simple-aggressive | Pressure ~1.8 | Pressure ~0.6 | 67% ↓ |
| simple-learning | Pressure ~2.2 | Pressure ~1.0 | 55% ↓ |
| strong-decision | Pressure ~1.5 | Pressure ~0.3 | 80% ↓ |

### Slow Leak Scenario
| Agent | Before | After | Improvement |
|-------|--------|-------|-------------|
| simple-adaptive | Actions: 12 | Actions: 8 | 33% ↓ |
| simple-learning | Necessary: 0.4 | Necessary: 0.65 | 63% ↑ |
| strong-decision | Reward: 45 | Reward: 65 | 44% ↑ |

---

## Regression Testing

After tuning, verify no regressions:

```python
# Test 1: Stable state should remain stable
# Pressure < 0.3, no actions needed
# Expected: noop actions, no intervention

# Test 2: Mild pressure should not over-react
# Pressure 0.5-0.8, should throttle not restart
# Expected: throttle action, not restart

# Test 3: Budget constraints still respected
# Should not exceed budget
# Expected: action rejection when budget exhausted

# Test 4: Action locks still enforced
# Should not act on same target twice in lock period
# Expected: noop or different target
```

---

## Monitoring During Testing

### Key Metrics to Watch
```
Per-step:
  - system_pressure (should decrease in crisis)
  - instability_score (should not spike)
  - action_type (should be appropriate for state)
  - reward (should be positive overall)

Per-episode:
  - total_reward (should increase over episodes)
  - necessary_action_ratio (should increase)
  - positive_impact_rate (should increase)
  - final_pressure (should be < 0.5)
```

### Logging Recommendations
```python
# Add logging to track:
print(f"Step {step}: pressure={pressure:.2f}, action={action['type']}, reward={reward:.2f}")
print(f"Episode {episode}: total_reward={total_reward:.2f}, necessary_ratio={ratio:.2f}")
```

---

## Success Criteria

### Firestorm Success
- ✅ Final pressure < 0.5
- ✅ Instability score < 0.2
- ✅ Stability score > 0.7
- ✅ Reaches stable state within 40 steps

### Slow Leak Success
- ✅ Necessary action ratio > 0.6
- ✅ Positive impact rate > 0.65
- ✅ Total actions < 12
- ✅ Final pressure < 0.4

### Ghost Spike Success
- ✅ Handles spike without collapse
- ✅ Recovery within 20 steps
- ✅ Instability < 0.3 at end
- ✅ Stability > 0.7 at end

---

## Next Steps

1. Run baseline tests with all agents on all tasks
2. Compare metrics to expected values
3. Identify any agents/tasks that underperform
4. Adjust specific parameters if needed
5. Re-run tests to validate improvements
6. Document final performance metrics
