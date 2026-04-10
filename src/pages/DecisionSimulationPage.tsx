import { useEffect, useMemo, useState } from "react";

import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { PageContainer } from "../components/ui/PageContainer";
import { Section } from "../components/ui/Section";
import { formatActionLabel } from "../lib/decision";
import { formatNumber, formatTarget } from "../lib/format";
import type {
  AgentAction,
  AutoRunnerStatus,
  Observation,
  PendingEffect,
  QueueKey,
  RecommendationResponse,
  TaskMap,
} from "../lib/types";

const queueOrder: QueueKey[] = ["A", "B", "C"];

type DecisionSimulationPageProps = {
  observation: Observation;
  tasks: TaskMap;
  selectedTask: string | null;
  loading: boolean;
  autoStatus: AutoRunnerStatus;
  recommendation: RecommendationResponse | null;
  onReset: (taskId?: string) => void;
  onManualStep: (action: AgentAction) => void;
  onApplyRecommendation: () => void;
  onStartAuto: () => void;
  onStopAuto: () => void;
};

function getQueueWidth(value: number, capacity: number) {
  if (capacity <= 0) return 0;
  return Math.min(100, (value / capacity) * 100);
}

function effectKey(effect: PendingEffect) {
  return `${effect.type}-${effect.target ?? "system"}-${effect.apply_at}-${effect.magnitude ?? 0}`;
}

function getDriftLabel(driftScore: number) {
  if (driftScore < 0.1) return "Stable";
  if (driftScore < 0.3) return "Low latent risk";
  if (driftScore < 0.6) return "Accumulating risk";
  return "Critical latent instability";
}

export function DecisionSimulationPage({
  observation,
  tasks,
  selectedTask,
  loading,
  autoStatus,
  recommendation,
  onReset,
  onManualStep,
  onApplyRecommendation,
  onStartAuto,
  onStopAuto,
}: DecisionSimulationPageProps) {
  const currentTimestep = observation.timestep ?? 0;
  const driftScore = Number(observation.drift_score ?? 0);
  const driftLabel = getDriftLabel(driftScore);
  const normalizedPendingEffects = useMemo<PendingEffect[]>(
    () =>
      (observation.pending_effects?.length
        ? observation.pending_effects.map((effect) => ({
            type: effect.type,
            target: effect.target ?? null,
            magnitude: effect.magnitude,
            apply_at: effect.apply_at,
          }))
        : (observation.pending_actions ?? []).map((effect) => ({
            type: effect.type,
            target: effect.target ?? null,
            magnitude: effect.magnitude,
            apply_at: effect.applies_at,
          }))),
    [observation.pending_actions, observation.pending_effects],
  );
  const [triggeredEffects, setTriggeredEffects] = useState<PendingEffect[]>([]);

  useEffect(() => {
    setTriggeredEffects([]);
  }, [currentTimestep]);

  useEffect(() => {
    const currentKeys = new Set(normalizedPendingEffects.map(effectKey));
    const previousEffects = (DecisionSimulationPage as unknown as {
      _previousPendingEffects?: PendingEffect[];
    })._previousPendingEffects ?? [];
    const justTriggered = previousEffects.filter((effect) => !currentKeys.has(effectKey(effect)));

    if (justTriggered.length > 0) {
      setTriggeredEffects(justTriggered);
      const timer = window.setTimeout(() => setTriggeredEffects([]), 1200);
      (DecisionSimulationPage as unknown as {
        _previousPendingEffects?: PendingEffect[];
      })._previousPendingEffects = normalizedPendingEffects;
      return () => window.clearTimeout(timer);
    }

    (DecisionSimulationPage as unknown as {
      _previousPendingEffects?: PendingEffect[];
    })._previousPendingEffects = normalizedPendingEffects;
    return undefined;
  }, [normalizedPendingEffects]);

  return (
    <PageContainer
      title="Simulation"
      subtitle="Step through the environment manually, use the operator recommendation, and watch delayed consequences unfold."
    >
      <Section
        title="Scenario control"
        description="Choose a task configuration and reset the environment into a deterministic operating condition."
      >
        <Card className="shadow-sm">
          <div className="space-y-4">
            <div className="flex flex-wrap gap-3">
              {Object.entries(tasks).map(([taskId, task]) => (
                <Button
                  key={taskId}
                  disabled={loading}
                  variant={selectedTask === taskId ? "primary" : "secondary"}
                  onClick={() => onReset(taskId)}
                >
                  {task.name}
                </Button>
              ))}
              <Button disabled={loading} variant="secondary" onClick={() => onReset()}>
                Reset default
              </Button>
            </div>

            {selectedTask && tasks[selectedTask] ? (
              <div className="rounded-xl border border-[#2a3039] bg-[#171c24] p-4">
                <p className="text-[14px] font-medium text-white">{tasks[selectedTask].name}</p>
                <p className="mt-1 text-[14px] leading-6 text-gray-400">{tasks[selectedTask].description}</p>
              </div>
            ) : null}
          </div>
        </Card>
      </Section>

      <div className="grid gap-5 xl:grid-cols-12">
        <div className="xl:col-span-7">
          <Section title="Manual controls" description="Step directly or apply the current operator recommendation.">
            <div className="space-y-4">
              <Card className="shadow-sm">
                <div className="space-y-4">
                  <div className="flex flex-wrap gap-3">
                    <Button disabled={loading || autoStatus.running} variant="primary" onClick={onApplyRecommendation}>
                      Use recommendation
                    </Button>
                    <Button
                      disabled={loading || autoStatus.running}
                      variant="secondary"
                      onClick={() => onManualStep({ type: "noop", target: null })}
                    >
                      Step noop
                    </Button>
                  </div>

                  <div className="space-y-4">
                    {queueOrder.map((target) => (
                      <div key={target} className="space-y-2 rounded-xl border border-[#2a3039] bg-[#171c24] p-4">
                        <div className="flex items-center justify-between">
                          <p className="text-[14px] font-medium text-white">Service {target}</p>
                          <p className="text-[12px] text-gray-400">
                            Queue {formatNumber(observation.queues[target], 1)} / Cap{" "}
                            {formatNumber(observation.capacities?.[target], 0)}
                          </p>
                        </div>
                        <div className="flex flex-wrap gap-3">
                          <Button disabled={loading || autoStatus.running} variant="secondary" onClick={() => onManualStep({ type: "restart", target })}>
                            Restart {target}
                          </Button>
                          <Button disabled={loading || autoStatus.running} variant="secondary" onClick={() => onManualStep({ type: "scale", target })}>
                            Scale {target}
                          </Button>
                          <Button disabled={loading || autoStatus.running} variant="secondary" onClick={() => onManualStep({ type: "throttle", target })}>
                            Throttle {target}
                          </Button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </Card>

              <Card className="shadow-sm">
                <div className="space-y-4">
                  <div className="space-y-1">
                    <p className="text-[11px] font-medium uppercase tracking-[0.16em] text-gray-400">Auto mode</p>
                    <p className="text-[14px] text-gray-400">
                      Run the current agent continuously on the selected scenario with fixed-interval stepping.
                    </p>
                  </div>

                  <div className="grid gap-4 md:grid-cols-2">
                    <div className="rounded-xl border border-[#2a3039] bg-[#171c24] p-4">
                      <p className="text-[13px] text-gray-400">Runner status</p>
                      <p className="mt-2 text-base font-semibold text-white">
                        {autoStatus.running ? "Running" : autoStatus.stop_reason === "done" ? "Completed" : "Stopped"}
                      </p>
                      <p className="mt-1 text-[13px] text-gray-400">
                        Agent {autoStatus.agent_name ?? "unknown"} · {autoStatus.steps_run ?? 0} steps
                      </p>
                    </div>
                    <div className="rounded-xl border border-[#2a3039] bg-[#171c24] p-4">
                      <p className="text-[13px] text-gray-400">Last action</p>
                      <p className="mt-2 text-base font-semibold text-white">
                        {autoStatus.last_action ? formatActionLabel(autoStatus.last_action) : "No actions yet"}
                      </p>
                      <p className="mt-1 text-[13px] text-gray-400">
                        Interval {(autoStatus.interval ?? 0.5).toFixed(1)}s
                      </p>
                    </div>
                  </div>

                  <div className="flex flex-wrap gap-3">
                    <Button disabled={loading || autoStatus.running} variant="primary" onClick={onStartAuto}>
                      Start auto
                    </Button>
                    <Button disabled={loading || !autoStatus.running} variant="secondary" onClick={onStopAuto}>
                      Stop auto
                    </Button>
                  </div>
                </div>
              </Card>
            </div>
          </Section>
        </div>

        <div className="xl:col-span-5">
          <Section title="Live system view" description="Current queue state, pending delayed effects, and operator recommendation.">
            <div className="space-y-4">
              <Card className="shadow-sm">
                <div className="space-y-4">
                  {queueOrder.map((queue) => {
                    const queueValue = Number(observation.queues[queue] ?? 0);
                    const capacityValue = Number(observation.capacities?.[queue] ?? 0);
                    const width = getQueueWidth(queueValue, capacityValue);

                    return (
                      <div key={queue} className="space-y-2">
                        <div className="flex items-center justify-between">
                          <p className="text-[14px] font-medium text-white">Queue {queue}</p>
                          <p className="text-[12px] text-gray-400">
                            {formatNumber(queueValue, 1)} / {formatNumber(capacityValue, 0)}
                          </p>
                        </div>
                        <div className="h-3 rounded-full bg-[#232935]">
                          <div className="h-3 rounded-full bg-[#C38EB4] transition-all duration-300" style={{ width: `${Math.max(width, width > 0 ? 6 : 0)}%` }} />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </Card>

              <Card className="shadow-sm">
                <div className="space-y-4">
                  <p className="text-[11px] font-medium uppercase tracking-[0.16em] text-gray-400">Latent instability</p>
                  <div className="grid gap-4 sm:grid-cols-2">
                    <div className="rounded-xl border border-[#2a3039] bg-[#171c24] p-4">
                      <p className="text-[13px] text-gray-400">Drift score</p>
                      <p className="mt-2 text-[22px] font-semibold tracking-[-0.02em] text-white">{formatNumber(driftScore, 2)}</p>
                      <p className="mt-1 text-[13px] font-medium text-[#C38EB4]">{driftLabel}</p>
                      <p className="mt-1 text-[13px] leading-6 text-gray-400">Slow risk accumulation while the system still looks calm.</p>
                    </div>
                    <div className="rounded-xl border border-[#2a3039] bg-[#171c24] p-4">
                      <p className="text-[13px] text-gray-400">Steps since action</p>
                      <p className="mt-2 text-[22px] font-semibold tracking-[-0.02em] text-white">{observation.steps_since_action ?? 0}</p>
                      <p className="mt-1 text-[13px] leading-6 text-gray-400">Consecutive timesteps without a non-noop intervention.</p>
                    </div>
                  </div>
                </div>
              </Card>

              <Card className="shadow-sm">
                <div className="space-y-3">
                  <p className="text-[11px] font-medium uppercase tracking-[0.16em] text-gray-400">Pending delayed effects</p>
                  {triggeredEffects.length > 0 ? (
                    <div className="space-y-2">
                      {triggeredEffects.map((effect, index) => (
                        <div key={`triggered-${effectKey(effect)}-${index}`} className="animate-pulse rounded-xl border border-emerald-900/40 bg-emerald-500/10 p-4 text-emerald-200 shadow-sm transition-all duration-300">
                          <p className="text-[14px] font-medium">{effect.type.toUpperCase()} on {formatTarget(effect.target)} triggered now</p>
                        </div>
                      ))}
                    </div>
                  ) : null}

                  {normalizedPendingEffects.length > 0 ? (
                    normalizedPendingEffects.map((pendingEffect, index) => {
                      const stepsUntilApply = pendingEffect.apply_at - currentTimestep;
                      const isDueNow = stepsUntilApply <= 0;

                      return (
                        <div
                          key={`${effectKey(pendingEffect)}-${index}`}
                        className={`rounded-xl border p-4 transition-all duration-300 ${isDueNow ? "border-[#C38EB4]/40 bg-[#C38EB4]/10 shadow-sm" : "border-[#2a3039] bg-[#171c24]"}`}
                        >
                          <p className="text-[14px] font-medium text-white">
                            {pendingEffect.type.toUpperCase()} on {formatTarget(pendingEffect.target)}
                          </p>
                          <p className="mt-1 text-[13px] text-gray-400">
                            {pendingEffect.type} {"->"} {formatTarget(pendingEffect.target)} @ t+{Math.max(0, stepsUntilApply)}
                          </p>
                          <p className="mt-1 text-[11px] uppercase tracking-[0.12em] text-gray-500">Applies at timestep {pendingEffect.apply_at}</p>
                        </div>
                      );
                    })
                  ) : (
                    <p className="text-[14px] text-gray-400">No delayed actions are queued.</p>
                  )}
                </div>
              </Card>

              <Card className="shadow-sm">
                <div className="space-y-2">
                  <p className="text-[11px] font-medium uppercase tracking-[0.16em] text-gray-400">Current recommendation</p>
                  <p className="text-base font-semibold text-white">
                    {recommendation ? formatActionLabel(recommendation.action) : "No recommendation loaded"}
                  </p>
                  <p className="text-[14px] leading-6 text-gray-400">
                    {recommendation?.reasoning.explanation ?? "Request a recommendation to inspect the best action."}
                  </p>
                </div>
              </Card>
            </div>
          </Section>
        </div>
      </div>
    </PageContainer>
  );
}
