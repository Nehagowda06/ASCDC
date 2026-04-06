import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { PageContainer } from "../components/ui/PageContainer";
import { Section } from "../components/ui/Section";
import { formatActionLabel } from "../lib/decision";
import { formatNumber, formatTarget } from "../lib/format";
import type { AgentAction, Observation, QueueKey, RecommendationResponse, TaskMap } from "../lib/types";

const queueOrder: QueueKey[] = ["A", "B", "C"];

type DecisionSimulationPageProps = {
  observation: Observation;
  tasks: TaskMap;
  selectedTask: string | null;
  loading: boolean;
  recommendation: RecommendationResponse | null;
  onReset: (taskId?: string) => void;
  onManualStep: (action: AgentAction) => void;
  onApplyRecommendation: () => void;
};

function getQueueWidth(value: number, capacity: number) {
  if (capacity <= 0) {
    return 0;
  }
  return Math.min(100, (value / capacity) * 100);
}

export function DecisionSimulationPage({
  observation,
  tasks,
  selectedTask,
  loading,
  recommendation,
  onReset,
  onManualStep,
  onApplyRecommendation,
}: DecisionSimulationPageProps) {
  return (
    <PageContainer
      title="Simulation"
      subtitle="Step through the environment manually, use the operator recommendation, and watch delayed consequences unfold."
    >
      <Section title="Scenario control" description="Choose a task configuration and reset the environment into a deterministic operating condition.">
        <Card className="shadow-sm">
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
        </Card>
      </Section>

      <div className="grid gap-6 xl:grid-cols-[1fr_0.9fr]">
        <Section title="Manual controls" description="Step directly or apply the current operator recommendation.">
          <Card className="shadow-sm">
            <div className="space-y-6">
              <div className="flex flex-wrap gap-3">
                <Button disabled={loading} variant="primary" onClick={onApplyRecommendation}>
                  Use recommendation
                </Button>
                <Button
                  disabled={loading}
                  variant="secondary"
                  onClick={() => onManualStep({ type: "noop", target: null })}
                >
                  Step noop
                </Button>
              </div>

              <div className="space-y-4">
                {queueOrder.map((target) => (
                  <div key={target} className="space-y-3 rounded-2xl border border-gray-200 bg-gray-50 p-4">
                    <div className="flex items-center justify-between">
                      <p className="text-sm font-medium text-gray-900">Service {target}</p>
                      <p className="text-xs text-gray-500">
                        Queue {formatNumber(observation.queues[target], 1)} / Cap {formatNumber(observation.capacities?.[target], 0)}
                      </p>
                    </div>
                    <div className="flex flex-wrap gap-3">
                      <Button
                        disabled={loading}
                        variant="secondary"
                        onClick={() => onManualStep({ type: "restart", target })}
                      >
                        Restart {target}
                      </Button>
                      <Button
                        disabled={loading}
                        variant="primary"
                        onClick={() => onManualStep({ type: "scale", target })}
                      >
                        Scale {target}
                      </Button>
                      <Button
                        disabled={loading}
                        variant="secondary"
                        onClick={() => onManualStep({ type: "throttle", target })}
                      >
                        Throttle {target}
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </Card>
        </Section>

        <Section title="Live system view" description="Current queue state, pending delayed effects, and operator recommendation.">
          <div className="space-y-6">
            <Card className="shadow-sm">
              <div className="space-y-4">
                {queueOrder.map((queue) => {
                  const queueValue = Number(observation.queues[queue] ?? 0);
                  const capacityValue = Number(observation.capacities?.[queue] ?? 0);
                  const width = getQueueWidth(queueValue, capacityValue);
                  return (
                    <div key={queue} className="space-y-2">
                      <div className="flex items-center justify-between">
                        <p className="text-sm font-medium text-gray-900">Queue {queue}</p>
                        <p className="text-xs text-gray-500">
                          {formatNumber(queueValue, 1)} / {formatNumber(capacityValue, 0)}
                        </p>
                      </div>
                      <div className="h-3 rounded-full bg-gray-100">
                        <div
                          className="h-3 rounded-full bg-blue-500 transition-all duration-300"
                          style={{ width: `${Math.max(width, width > 0 ? 6 : 0)}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </Card>

            <Card className="shadow-sm">
              <div className="space-y-3">
                <p className="text-xs font-medium uppercase tracking-[0.2em] text-gray-400">
                  Pending delayed effects
                </p>
                {observation.pending_actions && observation.pending_actions.length > 0 ? (
                  observation.pending_actions.map((pendingAction, index) => (
                    <div key={`${pendingAction.type}-${pendingAction.applies_at}-${index}`} className="rounded-2xl border border-gray-200 bg-gray-50 p-4">
                      <p className="text-sm font-medium text-gray-900">
                        {pendingAction.type.toUpperCase()} on {formatTarget(pendingAction.target)}
                      </p>
                      <p className="mt-1 text-sm text-gray-500">
                        Applies at timestep {pendingAction.applies_at}
                      </p>
                    </div>
                  ))
                ) : (
                  <p className="text-sm text-gray-500">No delayed actions are queued.</p>
                )}
              </div>
            </Card>

            <Card className="shadow-sm">
              <div className="space-y-2">
                <p className="text-xs font-medium uppercase tracking-[0.2em] text-gray-400">
                  Current recommendation
                </p>
                <p className="text-lg font-semibold text-gray-900">
                  {recommendation ? formatActionLabel(recommendation.action) : "No recommendation loaded"}
                </p>
                <p className="text-sm text-gray-500">
                  {recommendation?.reasoning.explanation ?? "Request a recommendation to inspect the best action."}
                </p>
              </div>
            </Card>
          </div>
        </Section>
      </div>
    </PageContainer>
  );
}
