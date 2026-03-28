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
  efficiency: number;
  collapsed: boolean;
  steps: number;
};

function buildBreakdown(trajectory: TrajectoryStep[]): Breakdown {
  if (trajectory.length === 0) {
    return {
      stability: 0,
      precision: 0,
      efficiency: 0,
      collapsed: false,
      steps: 0,
    };
  }

  const latencies = trajectory.map((step) => Number(step.info.latency ?? 0));
  const avgLatency = latencies.reduce((total, value) => total + value, 0) / trajectory.length;
  const stability = Math.max(0, 1 - avgLatency / 10);

  let totalActions = 0;
  let overreactions = 0;
  let successfulActions = 0;

  trajectory.forEach((step) => {
    if (step.action.type === "noop") {
      return;
    }

    totalActions += 1;

    const pressureDelta = Number(step.info.pressure_delta ?? 0);
    const systemPressure = Number(step.info.system_pressure ?? 0);

    if (pressureDelta <= 0 && systemPressure < 0.8) {
      overreactions += 1;
    }

    const scheduledTimestep = step.info.scheduled_timestep;
    if (scheduledTimestep === undefined) {
      return;
    }

    const futureStep = trajectory.find((candidate) => candidate.timestep === scheduledTimestep);
    if (futureStep && Number(futureStep.info.system_pressure ?? 0) < systemPressure) {
      successfulActions += 1;
    }
  });

  const precision =
    totalActions === 0
      ? 1
      : Math.max(0, successfulActions / totalActions * (1 - overreactions / totalActions));

  const initialBudget = Number(trajectory[0]?.info.remaining_budget ?? 0);
  const finalBudget = Number(trajectory[trajectory.length - 1]?.info.remaining_budget ?? 0);
  const efficiency =
    initialBudget > 0 ? Math.max(0, Math.min(1, finalBudget / initialBudget)) : 0;

  return {
    stability,
    precision,
    efficiency,
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
    efficiency: 0,
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
            hint="Action discipline"
          />
          <MetricBox
            label="Efficiency"
            value={formatNumber(breakdown.efficiency, 4)}
            hint={breakdown.collapsed ? "Collapsed" : "No collapse"}
          />
        </div>
      </Section>
    </PageContainer>
  );
}
