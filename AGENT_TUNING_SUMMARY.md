# Agent Tuning & Improvements Summary

## Overview
Tuning agents to better handle turbulent scenarios while **preserving the core system design**:
- Delayed causality (3-2-1 step delays)
- Irreversible instability accumulation
- Counterfactual evaluation for decision necessity
- Planning-heavy decision making

The goal is to improve agent decision-making, not to make the environment easier.

---

## Environment (UNCHANGED)

The environment remains as designed:
- **SCALE_DELAY**: 3 steps (planning window required)
- **RESTART_DELAY**: 2 steps (consequences unfold)
- **THROTTLE_DELAY**: 1 step (gradual control)
- **INSTABILITY_GROWTH_RATE**: 0.45 (exponential, irreversible)

These delays force agents to plan ahead and evaluate counterfactuals properly.

---

## SimpleAgent Improvements

### Adaptive Strategy (Default)
**More aggressive thresholds for better decision-making:**
- Restart: 2.0 ratio → **1.8** (earlier restart)
- Scale: 0.95 ratio → **0.85** (earlier scaling)
- Added proactive throttle at 0.45 ratio + 0.7 pressure

### Conservative Strategy
**Balanced between safety and responsiveness:**
- Restart: 3.0 ratio → **2.5** (more responsive)
- Scale: 1.5 ratio → **1.3** (earlier intervention)
- Added throttle at 0.9 ratio (new)

### Aggressive Strategy
**Reordered for better crisis handling:**
- Restart: 2.5 ratio → **2.0** (more aggressive)
- Scale: 0.75 ratio → **0.65** (earlier)
- Throttle: 0.35 ratio → **0.3** (more proactive)

---

## LearningAgent Improvements (Major Overhaul)

### Better Q-Learning Parameters
- **Alpha (learning rate)**: 0.3 → **0.4** (faster learning)
- **Alpha decay**: 0.999 → **0.998** (slower decay, maintains learning)
- **Min alpha**: 0.05 → **0.08** (higher floor)
- **Gamma (discount)**: 0.9 → **0.95** (values future rewards more)
- **Epsilon (exploration)**: 0.2 → **0.25** (more exploration)
- **Epsilon decay**: 0.995 → **0.993** (slower decay)
- **Min epsilon**: 0.02 → **0.05** (more exploration in later episodes)
- **Max states**: 500 → **1000** (larger state space)

### Enhanced State Representation
**Old**: `(pressure_rounded_to_0.1, bottleneck_queue)`
**New**: `(pressure_bucket_0.5, bottleneck_queue, error_state)`

- Pressure quantized to 0.5 granularity (coarser, more generalizable)
- Added error state: "high" if retry_rate > 0.5 or error_rate > 0.3
- Enables learning different strategies for error-prone vs normal states

### Adaptive Learning Rate
- Learning rate now scales with reward magnitude: `alpha * (1.0 + 0.2 * min(|reward|, 2.0))`
- Larger rewards get faster updates (crisis learning)
- Smaller rewards get standard updates (fine-tuning)

### Pressure-Aware Exploration
- In crisis (pressure > 2.0): exploration reduced by 50% (exploit known good actions)
- In calm (pressure < 0.5): exploration increased by 20% (explore more)
- Balances exploitation in emergencies with exploration in stable states

### Episode Tracking
- Added `episode_count` and `step_count` for better monitoring
- Enables future curriculum learning or adaptive scheduling

---

## SmartAgent (Strong-Decision) Improvements

### Increased Lookahead
- **Horizon**: 10 → **12** (20% longer planning)
- Maintains planning-heavy nature while seeing more consequences

### Improved Scoring
- Instability penalty: -0.4 for noop when instability > 0.4 (new)
- Crisis bonus: +0.8 for action when pressure > 2.0 (was +1.0, kept reasonable)
- Prevents premature action in calm states: -0.3 (unchanged)

### Better Thresholds
- Proactive mode trigger: 0.15 → **0.15** (unchanged, preserves design)
- Proactive mode exit: 0.05 → **0.05** (unchanged)
- Stable state pressure: 0.4 → **0.4** (unchanged)
- Stable state drift: 0.03 → **0.03** (unchanged)
- Queue persistence threshold: 4 → **4** (unchanged)

### Proactive Action Improvements
- Throttle for instability without high pressure (pressure < 1.0, instability > 0.3)
- Maintains original logic, just better tuned

---

## Key Improvements Summary

| Aspect | Change | Benefit |
|--------|--------|---------|
| **SimpleAgent** | Lower thresholds | Better decision timing |
| **LearningAgent** | Better state representation + adaptive learning | Learns crisis patterns faster |
| **SmartAgent** | Longer lookahead + better scoring | Better planning through delays |
| **Environment** | UNCHANGED | Preserves delayed causality & counterfactual evaluation |

---

## What Was NOT Changed

✅ **Delayed causality** - Actions still take 1-3 steps to apply
✅ **Irreversible instability** - Still accumulates exponentially
✅ **Counterfactual evaluation** - Still measures decision necessity
✅ **Planning requirement** - Agents still must look ahead
✅ **Budget constraints** - Still limited resources
✅ **Action locks** - Still prevent rapid re-intervention

---

## Expected Improvements

### Firestorm Scenario
- ✅ Better decision timing through improved thresholds
- ✅ SmartAgent plans better through longer horizon
- ✅ LearningAgent learns crisis patterns faster
- ✅ System still requires planning, but agents are smarter

### Slow Leak Scenario
- ✅ LearningAgent learns to throttle early
- ✅ Proactive mode triggers appropriately
- ✅ Better drift detection through learning

### Ghost Spike Scenario
- ✅ Better handling through improved scoring
- ✅ Faster learning of spike patterns
- ✅ Better instability management

---

## Testing Recommendations

1. **Run Firestorm with strong-decision**: Should reach stable state through better planning
2. **Run Slow Leak with simple-learning**: Should learn to throttle early
3. **Compare metrics**: Check necessary_action_ratio and positive_impact_rate
4. **Monitor instability**: Should see better management through improved decisions

---

## Future Improvements

- Curriculum learning: Start with Slow Leak, progress to Firestorm
- Experience replay: Store and replay high-reward trajectories
- Double Q-learning: Reduce overestimation bias
- Dueling networks: Separate value and advantage streams
- Policy gradient: For continuous action spaces

