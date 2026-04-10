import { useState } from "react";

import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { MetricBox } from "../components/ui/MetricBox";
import { PageContainer } from "../components/ui/PageContainer";
import { Section } from "../components/ui/Section";
import { gradeTrajectory } from "../lib/api";
import { formatNumber } from "../lib/format";
import type { TrajectoryStep } from "../lib/types";

type Breakdown = {
  stability: number;
  precision: number;
  smoothness: number;
  collapsed: boolean;
  steps: number;
};

const MAX_LATENCY = 10;
const CRITICAL_PRESSURE = 3;
const PRESSURE_INCREASE_THRESHOLD = 0.12;
const SMALL_PRESSURE_THRESHOLD = 0.05;
const STABILIZATION_HORIZON = 3;

function clamp(value: number): number {
  return Math.max(0, Math.min(1, value));
}

function getPressure(step: TrajectoryStep, index: number, trajectory: TrajectoryStep[]): number {
  const nextPressure = Number(
    step.next_observation?.system_pressure
      ?? step.info.system_pressure
      ?? (step.info as Record<string, unknown>).pressure
      ?? NaN,
  );

  if (Number.isFinite(nextPressure)) {
    return nextPressure;
  }

  const observationPressure = Number(
    step.observation?.system_pressure
      ?? (step.observation as Record<string, unknown>)?.pressure
      ?? NaN,
  );

  if (Number.isFinite(observationPressure)) {
    return observationPressure;
  }

  return index > 0 ? getPressure(trajectory[index - 1], index - 1, trajectory) : 0;
}

function getPressureDelta(step: TrajectoryStep, index: number, trajectory: TrajectoryStep[]): number {
  const beforePressure = Number(
    step.observation?.system_pressure
      ?? (step.observation as Record<string, unknown>)?.pressure
      ?? NaN,
  );
  const afterPressure = getPressure(step, index, trajectory);

  if (Number.isFinite(beforePressure)) {
    return afterPressure - beforePressure;
  }

  if (index === 0) {
    return 0;
  }

  return afterPressure - getPressure(trajectory[index - 1], index - 1, trajectory);
}

function buildBreakdown(trajectory: TrajectoryStep[]): Breakdown {
  if (trajectory.length === 0) {
    return {
      stability: 0,
      precision: 0,
      smoothness: 0,
      collapsed: false,
      steps: 0,
    };
  }

  const latencies = trajectory.map((step) => Number(step.info.latency ?? 0));
  const pressures = trajectory.map((step, index) => getPressure(step, index, trajectory));
  const pressureDeltas = trajectory.map((step, index) => getPressureDelta(step, index, trajectory));
  const avgLatency = latencies.reduce((total, value) => total + value, 0) / trajectory.length;
  const avgPressure = pressures.reduce((total, value) => total + value, 0) / trajectory.length;
  const latencyScore = clamp(1 - avgLatency / MAX_LATENCY);
  const pressureScore = clamp(1 - avgPressure / CRITICAL_PRESSURE);
  const stability = clamp(0.55 * latencyScore + 0.45 * pressureScore);

  let totalActions = 0;
  let actionableMoments = 0;
  let missedInterventions = 0;
  let unnecessaryActions = 0;
  let timelyActions = 0;

  trajectory.forEach((step, index) => {
    const actionType = step.action.type ?? "noop";
    const pressureDelta = pressureDeltas[index];

    if (pressureDelta > PRESSURE_INCREASE_THRESHOLD) {
      actionableMoments += 1;
      if (actionType === "noop") {
        missedInterventions += 1;
      }
    }

    if (actionType === "noop") {
      return;
    }

    totalActions += 1;

    if (pressureDelta < SMALL_PRESSURE_THRESHOLD) {
      unnecessaryActions += 1;
    }

    const currentPressure = pressures[index];
    const futureWindow = pressures.slice(index + 1, index + 1 + STABILIZATION_HORIZON);
    const stabilizesEarly = futureWindow.some(
      (futurePressure) => futurePressure < currentPressure - SMALL_PRESSURE_THRESHOLD,
    );

    if (stabilizesEarly) {
      timelyActions += 1;
    }
  });

  const missedPenalty = actionableMoments > 0 ? missedInterventions / actionableMoments : 0;
  const unnecessaryPenalty = totalActions > 0 ? unnecessaryActions / totalActions : 0;
  const timelyReward = totalActions > 0 ? timelyActions / totalActions : 0.5;
  const precision = clamp(0.35 + 0.45 * timelyReward - 0.35 * missedPenalty - 0.25 * unnecessaryPenalty);

  const significantSigns = pressureDeltas
    .filter((delta) => Math.abs(delta) >= SMALL_PRESSURE_THRESHOLD)
    .map((delta) => (delta > 0 ? 1 : -1));
  let signFlips = 0;
  for (let index = 1; index < significantSigns.length; index += 1) {
    if (significantSigns[index] !== significantSigns[index - 1]) {
      signFlips += 1;
    }
  }
  const pressureOscillationPenalty = significantSigns.length > 1
    ? signFlips / Math.max(1, significantSigns.length - 1)
    : 0;

  const nonNoopActions = trajectory
    .map((step) => {
      const actionType = step.action.type ?? "noop";
      if (actionType === "noop") {
        return null;
      }
      const target = step.action.target ?? "";
      return `${String(actionType).toUpperCase()} ${target}`.trim();
    })
    .filter((value): value is string => value !== null);
  let actionFlips = 0;
  for (let index = 1; index < nonNoopActions.length; index += 1) {
    if (nonNoopActions[index] !== nonNoopActions[index - 1]) {
      actionFlips += 1;
    }
  }
  const actionOscillationPenalty = nonNoopActions.length > 1
    ? actionFlips / Math.max(1, nonNoopActions.length - 1)
    : 0;
  const smoothness = clamp(1 - (0.75 * pressureOscillationPenalty + 0.25 * actionOscillationPenalty));

  return {
    stability,
    precision,
    smoothness,
    collapsed: trajectory.some((step) => Boolean(step.info.failure_flags?.collapsed)),
    steps: trajectory.length,
  };
}

export function GraderPage() {
  const [input, setInput] = useState("[]");
  const [score, setScore] = useState<number | null>(null);
  const [breakdown, setBreakdown] = useState<Breakdown>({
    stability: 0,
    precision: 0,
    smoothness: 0,
    collapsed: false,
    steps: 0,
  });
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleGrade() {
    setLoading(true);
    try {
      const trajectory = JSON.parse(input) as TrajectoryStep[];
      if (!Array.isArray(trajectory)) {
        throw new Error("Trajectory must be a JSON array.");
      }

      const response = await gradeTrajectory(trajectory);
      setScore(response.score);
      setBreakdown(buildBreakdown(trajectory));
      setError(null);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Unable to grade trajectory.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <PageContainer
      title="Grader"
      subtitle="Paste a trajectory, submit it once, and inspect the resulting score breakdown."
    >
      {error ? <p className="text-sm text-red-500">{error}</p> : null}

      <Section title="Trajectory input" description="Use raw JSON from a runner episode or custom evaluation flow.">
        <Card>
          <div className="space-y-4">
            <textarea
              className="min-h-64 w-full rounded-xl border border-gray-200 bg-white p-4 text-sm text-gray-900 outline-none transition-colors focus:border-blue-600"
              spellCheck={false}
              value={input}
              onChange={(event) => setInput(event.target.value)}
            />
            <div className="flex flex-wrap gap-4">
              <Button disabled={loading} variant="primary" onClick={handleGrade}>
                Grade trajectory
              </Button>
            </div>
          </div>
        </Card>
      </Section>

      <Section title="Breakdown" description="The summary stays focused on the scoring rubric only.">
        <div className="grid gap-4 md:grid-cols-4">
          <MetricBox
            label="Overall score"
            value={score === null ? "0.0000" : score.toFixed(4)}
            hint={`${breakdown.steps} steps`}
          />
          <MetricBox
            label="Stability"
            value={formatNumber(breakdown.stability, 4)}
            hint="Latency resilience"
          />
          <MetricBox
            label="Precision"
            value={formatNumber(breakdown.precision, 4)}
            hint="Timing quality"
          />
          <MetricBox
            label="Smoothness"
            value={formatNumber(breakdown.smoothness, 4)}
            hint={breakdown.collapsed ? "Collapsed" : "Low oscillation"}
          />
        </div>
      </Section>
    </PageContainer>
  );
}
