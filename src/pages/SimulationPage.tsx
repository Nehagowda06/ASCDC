import { useEffect, useRef, useState } from "react";
import {
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Button } from "../components/ui/Button";
import { ChartWrapper } from "../components/ui/ChartWrapper";
import { Card } from "../components/ui/Card";
import { MetricBox } from "../components/ui/MetricBox";
import { PageContainer } from "../components/ui/PageContainer";
import { Section } from "../components/ui/Section";
import { fetchState, stepEnvironment } from "../lib/api";
import { formatNumber, formatTarget } from "../lib/format";
import {
  EMPTY_OBSERVATION,
  type AgentAction,
  type Observation,
  type PendingAction,
} from "../lib/types";

type HistoryPoint = {
  step: number;
  latency: number;
};

const queueOrder = ["A", "B", "C"] as const;

function getPressureState(pressure: number | undefined) {
  if ((pressure ?? 0) >= 2) {
    return {
      label: "Critical",
      pillClassName: "bg-red-500/10 text-red-600",
      dotClassName: "bg-red-500",
      hint: "Latency + retries increasing",
    };
  }

  if ((pressure ?? 0) >= 1) {
    return {
      label: "Warning",
      pillClassName: "bg-yellow-500/10 text-yellow-600",
      dotClassName: "bg-yellow-500",
      hint: "Queue B rising",
    };
  }

  return {
    label: "Stable",
    pillClassName: "bg-green-500/10 text-green-600",
    dotClassName: "bg-green-500",
    hint: "Queues within capacity",
  };
}

function getQueueBarClassName(fill: number) {
  if (fill >= 0.85) {
    return "bg-red-500";
  }

  if (fill >= 0.55) {
    return "bg-yellow-500";
  }

  return "bg-green-500";
}

export function SimulationPage() {
  const [observation, setObservation] = useState<Observation>(EMPTY_OBSERVATION);
  const [history, setHistory] = useState<HistoryPoint[]>([]);
  const [target, setTarget] = useState<(typeof queueOrder)[number]>("A");
  const [selectedAction, setSelectedAction] = useState<AgentAction["type"]>("noop");
  const [isAutoRunning, setIsAutoRunning] = useState(false);
  const [highlightedQueue, setHighlightedQueue] = useState<(typeof queueOrder)[number] | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const highlightTimeoutRef = useRef<number | null>(null);

  useEffect(() => {
    let cancelled = false;

    fetchState()
      .then((nextObservation) => {
        if (!cancelled) {
          setObservation(nextObservation);
          setHistory([
            {
              step: nextObservation.timestep ?? 0,
              latency: nextObservation.latency ?? 0,
            },
          ]);
          setError(null);
        }
      })
      .catch((nextError: Error) => {
        if (!cancelled) {
          setError(nextError.message);
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    return () => {
      if (highlightTimeoutRef.current !== null) {
        window.clearTimeout(highlightTimeoutRef.current);
      }
    };
  }, []);

  useEffect(() => {
    if (!isAutoRunning || loading) {
      return;
    }

    const timer = window.setInterval(() => {
      void runStep(selectedAction);
    }, 1200);

    return () => {
      window.clearInterval(timer);
    };
  }, [isAutoRunning, loading, selectedAction, target]);

  async function runStep(actionType: AgentAction["type"]) {
    const action: AgentAction = {
      type: actionType,
      target: actionType === "noop" ? null : target,
    };

    if (action.target && queueOrder.includes(action.target as (typeof queueOrder)[number])) {
      setHighlightedQueue(action.target as (typeof queueOrder)[number]);
      if (highlightTimeoutRef.current !== null) {
        window.clearTimeout(highlightTimeoutRef.current);
      }
      highlightTimeoutRef.current = window.setTimeout(() => {
        setHighlightedQueue(null);
      }, 300);
    }

    setLoading(true);
    try {
      const response = await stepEnvironment(action);
      setObservation(response.observation);
      setHistory((current) => [
        ...current.slice(-19),
        {
          step: response.observation.timestep ?? current.length + 1,
          latency: Number(response.info.latency ?? 0),
        },
      ]);
      setError(null);
    } catch (nextError) {
      setIsAutoRunning(false);
      setError(nextError instanceof Error ? nextError.message : "Unable to step simulation.");
    } finally {
      setLoading(false);
    }
  }

  const pendingActions = observation.pending_actions ?? [];
  const pressureState = getPressureState(observation.system_pressure);

  return (
    <PageContainer
      title="Simulation"
      subtitle="Monitor queue pressure, apply one action profile, and watch the system respond in real time."
    >
      <div className="space-y-6 rounded-[24px] bg-gradient-to-br from-gray-50 to-white p-6">
        <div className="flex items-start justify-start">
          <div className="space-y-2">
            <div className={`flex items-center gap-2 rounded-full px-2 py-1 text-xs font-medium ${pressureState.pillClassName}`}>
              <div className={`h-2 w-2 rounded-full ${pressureState.dotClassName}`} />
              {pressureState.label}
            </div>
            <p className="text-xs text-gray-500">{pressureState.hint}</p>
          </div>
        </div>

        {error ? <p className="text-sm text-red-500">{error}</p> : null}

        <Section title="Controls" description="Choose a target and action profile, then step or run the system.">
          <Card>
            <div className="space-y-4">
              <div className="flex flex-wrap gap-4">
                {queueOrder.map((queue) => (
                  <Button
                    key={queue}
                    variant={target === queue ? "primary" : "secondary"}
                    onClick={() => setTarget(queue)}
                  >
                    Target {queue}
                  </Button>
                ))}
              </div>

              <div className="flex flex-wrap gap-4">
                <Button
                  disabled={loading}
                  variant={selectedAction === "restart" ? "danger" : "secondary"}
                  onClick={() => setSelectedAction("restart")}
                >
                  Restart
                </Button>
                <Button
                  disabled={loading}
                  variant={selectedAction === "scale" ? "primary" : "secondary"}
                  onClick={() => setSelectedAction("scale")}
                >
                  Scale
                </Button>
                <Button
                  disabled={loading}
                  variant={selectedAction === "throttle" ? "primary" : "secondary"}
                  onClick={() => setSelectedAction("throttle")}
                >
                  Throttle
                </Button>
                <Button
                  disabled={loading}
                  variant={selectedAction === "noop" ? "primary" : "secondary"}
                  onClick={() => setSelectedAction("noop")}
                >
                  Noop
                </Button>
              </div>

              <div className="flex flex-wrap gap-4">
                <Button disabled={loading} variant="primary" onClick={() => void runStep(selectedAction)}>
                  Step
                </Button>
                <Button
                  disabled={loading || isAutoRunning}
                  variant="secondary"
                  onClick={() => setIsAutoRunning(true)}
                >
                  Auto-run
                </Button>
                <Button
                  disabled={!isAutoRunning}
                  variant="danger"
                  onClick={() => setIsAutoRunning(false)}
                >
                  Pause
                </Button>
              </div>

              <div className="flex flex-wrap gap-4 text-sm text-gray-500">
                <p>
                  Selected action: <span className="text-gray-900">{selectedAction}</span>
                </p>
                <p>
                  Target: <span className="text-gray-900">{target}</span>
                </p>
                <p>
                  Mode: <span className="text-gray-900">{isAutoRunning ? "Auto-run" : "Manual"}</span>
                </p>
              </div>
            </div>
          </Card>
        </Section>

        <Section title="Snapshot" description="Queues and budget stay visible at the top of the screen.">
          <div className="grid gap-6 md:grid-cols-4">
            {queueOrder.map((queue) => (
              <MetricBox
                key={queue}
                label={`Queue ${queue}`}
                value={formatNumber(observation.queues[queue], 1)}
                hint={`Capacity ${formatNumber(observation.capacities?.[queue], 0)}`}
                className={queue === highlightedQueue ? "bg-blue-500/10 transition duration-300" : undefined}
              />
            ))}
            <MetricBox
              label="Remaining budget"
              tone="budget"
              value={formatNumber(observation.remaining_budget)}
              hint={`Pressure ${formatNumber(observation.system_pressure)}`}
              trend={(observation.remaining_budget ?? 0) > 50 ? "↑ healthy" : "↓ tighter"}
            />
          </div>
        </Section>

        <Section title="Queue load" description="Horizontal bars make queue imbalance visible at a glance.">
          <Card>
            <div className="space-y-6">
              <div>
                <h3 className="text-lg font-medium text-gray-900">Queue load</h3>
                <p className="text-sm text-gray-500">Horizontal bars show pressure against each service capacity.</p>
              </div>

              <div className="space-y-6">
                {queueOrder.map((queue) => {
                  const queueValue = Number(observation.queues[queue] ?? 0);
                  const capacityValue = Number(observation.capacities?.[queue] ?? 0);
                  const fill = capacityValue > 0 ? Math.min(queueValue / capacityValue, 1) : 0;

                  return (
                    <div
                      key={queue}
                      className={queue === highlightedQueue ? "space-y-2 rounded-xl bg-blue-500/10 p-4 transition duration-300" : "space-y-2"}
                    >
                      <div className="flex items-center justify-between">
                        <p className="text-sm font-medium text-gray-900">Queue {queue}</p>
                        <p className="text-sm text-gray-500">
                          {formatNumber(queueValue, 1)} / {formatNumber(capacityValue, 0)}
                        </p>
                      </div>
                      <div className="h-4 rounded-xl bg-gray-100">
                        <div
                          className={`h-4 rounded-xl transition-all duration-300 ${getQueueBarClassName(fill)}`}
                          style={{ width: fill === 0 ? "0%" : `${Math.max(fill * 100, 6)}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </Card>
        </Section>

        <Section title="Latency" description="The chart updates as each step resolves.">
          <ChartWrapper
            title="Latency trend"
            subtitle="Each point reflects the environment after one live step."
          >
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={history}>
                <XAxis
                  axisLine={false}
                  dataKey="step"
                  tickLine={false}
                  tick={{ fill: "#6b7280", fontSize: 12 }}
                />
                <YAxis
                  axisLine={false}
                  tickLine={false}
                  tick={{ fill: "#6b7280", fontSize: 12 }}
                />
                <Tooltip
                  contentStyle={{
                    borderRadius: 16,
                    borderColor: "#e5e7eb",
                    fontSize: 12,
                  }}
                />
                <Line
                  dataKey="latency"
                  dot={false}
                  stroke="#2563eb"
                  strokeWidth={2}
                  type="monotone"
                />
              </LineChart>
            </ResponsiveContainer>
          </ChartWrapper>
        </Section>

        <Section title="Pending actions" description="Delayed effects are shown as a simple timeline.">
          <Card>
            <div className="space-y-4">
              {pendingActions.length === 0 ? (
                <p className="text-sm text-gray-500">No delayed actions are queued.</p>
              ) : (
                pendingActions.map((row: PendingAction, index) => (
                  <div
                    key={`${row.type}-${row.target ?? "system"}-${row.applies_at}-${index}`}
                    className="flex flex-wrap items-center justify-between gap-4 border-t border-gray-100 pt-4 first:border-t-0 first:pt-0"
                  >
                    <div className="space-y-1">
                      <p className="text-sm font-medium text-gray-900">
                        {row.type} on {formatTarget(row.target)}
                      </p>
                      <p className="text-sm text-gray-500">Delayed effect waiting in the queue.</p>
                    </div>
                    <p className="text-sm text-gray-500">Timestep {row.applies_at}</p>
                  </div>
                ))
              )}
            </div>
          </Card>
        </Section>
      </div>
    </PageContainer>
  );
}
