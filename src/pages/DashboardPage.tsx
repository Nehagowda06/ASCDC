import { useEffect, useState } from "react";

import { Card } from "../components/ui/Card";
import { PageContainer } from "../components/ui/PageContainer";
import { Section } from "../components/ui/Section";
import { fetchState } from "../lib/api";
import { formatNumber, formatPercent } from "../lib/format";
import { EMPTY_STATE, type EnvironmentState } from "../lib/types";

const queueOrder = ["A", "B", "C"] as const;

function getQueueFill(queueValue: number, capacityValue: number) {
  if (capacityValue <= 0) {
    return 0;
  }

  return Math.max(0, Math.min(queueValue / capacityValue, 1));
}

function getQueueBarClassName(fill: number) {
  if (fill > 0.8) {
    return "bg-red-500";
  }

  if (fill >= 0.5) {
    return "bg-yellow-500";
  }

  return "bg-green-500";
}

function cleanPercent(value?: number) {
  if (!value || value < 0.01) {
    return 0;
  }

  return value;
}

function getSystemStatus(pressure: number | undefined, collapsed: boolean | undefined) {
  if (collapsed || (pressure ?? 0) >= 2) {
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

export function DashboardPage() {
  const [state, setState] = useState<EnvironmentState>(EMPTY_STATE);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    fetchState()
      .then((nextState) => {
        if (!cancelled) {
          setState(nextState);
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

  const systemStatus = getSystemStatus(
    state.system_pressure,
    state.failure_flags?.collapsed,
  );
  const highestLoadQueue = queueOrder.reduce<(typeof queueOrder)[number]>((currentMax, queue) => {
    const currentFill = getQueueFill(
      Number(state.queues[currentMax] ?? 0),
      Number(state.capacities?.[currentMax] ?? 0),
    );
    const nextFill = getQueueFill(
      Number(state.queues[queue] ?? 0),
      Number(state.capacities?.[queue] ?? 0),
    );

    return nextFill > currentFill ? queue : currentMax;
  }, "A");

  const topMetrics = [
    {
      label: "System pressure",
      value: formatNumber(state.system_pressure),
      hint: "Lower is more stable",
      dotClassName: (state.system_pressure ?? 0) >= 2
        ? "bg-red-500"
        : (state.system_pressure ?? 0) >= 1
          ? "bg-yellow-500"
          : "bg-yellow-400",
      valueClassName: (state.system_pressure ?? 0) >= 2
        ? "text-red-600"
        : (state.system_pressure ?? 0) >= 1
          ? "text-yellow-600"
          : "text-yellow-500",
    },
    {
      label: "Remaining budget",
      value: formatNumber(state.remaining_budget),
      hint: "Available for actions",
      dotClassName: "bg-green-500",
      valueClassName: "text-green-600",
    },
    {
      label: "Pending actions",
      value: String(state.pending_actions?.length ?? 0),
      hint: "Delayed effects waiting",
      dotClassName: "bg-gray-400",
      valueClassName: "text-gray-900",
    },
    {
      label: "Retry rate",
      value: formatPercent(cleanPercent(state.retry_rate)),
      hint: "Current amplification",
      dotClassName: "bg-blue-500",
      valueClassName: "text-blue-600",
    },
  ];

  const signalRows = [
    {
      label: "Retry rate",
      value: formatPercent(cleanPercent(state.retry_rate)),
      explanation: "Current amplification pressure across services.",
    },
    {
      label: "Error rate",
      value: formatPercent(cleanPercent(state.error_rate)),
      explanation: "Observed error pressure in the live system.",
    },
    {
      label: "Collapse status",
      value: state.failure_flags?.collapsed ? "Collapsed" : "Operational",
      explanation: "System-wide resilience flag for the current run.",
    },
  ];

  return (
    <PageContainer
      title="Dashboard"
      subtitle="A quiet overview of the current system posture, budget, and queue health."
    >
      <div className="space-y-8 rounded-xl bg-gray-100 p-6">
        {error ? <p className="text-sm text-red-500">{error}</p> : null}

        <div className="space-y-6 rounded-xl border border-gray-200 border-l-4 border-l-blue-500 bg-white p-8 shadow-sm">
          <div className="flex items-center justify-between gap-6">
            <div>
              <div className={`flex items-center gap-2 rounded-full px-3 py-1.5 text-xs font-medium shadow-sm ${systemStatus.pillClassName}`}>
                <div className={`h-2 w-2 rounded-full ${systemStatus.dotClassName}`} />
                {systemStatus.label}
              </div>
              <p className="mt-1 text-sm text-gray-500">{systemStatus.hint}</p>
            </div>

            <div className="rounded-lg bg-blue-50 px-3 py-2 text-right">
              <p className="text-xs text-gray-500">Latency</p>
              <p className="text-3xl font-semibold text-blue-600">{formatNumber(state.latency)}</p>
            </div>
          </div>

          <div className="rounded-lg bg-gray-50 p-4">
            <div className="grid gap-4 md:grid-cols-4">
              {topMetrics.map((metric) => (
                <div
                  key={metric.label}
                  className="rounded-xl border border-gray-200 bg-white/90 p-4 backdrop-blur transition-all duration-200 hover:scale-[1.01] hover:border-gray-300 hover:bg-white"
                >
                  <div className="space-y-2">
                    <div className="flex items-center gap-2">
                      <div className={`h-2 w-2 rounded-full ${metric.dotClassName}`} />
                      <p className="text-xs text-gray-500">{metric.label}</p>
                    </div>
                    <p className={`text-2xl font-semibold ${metric.valueClassName}`}>
                      {metric.value}
                    </p>
                    <p className="text-sm text-gray-500">{metric.hint}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        <div className="border-t border-gray-200 pt-6">
          <Section
            title="Current posture"
            description="Queue depth and system signals in one place."
          >
            <div className="space-y-6">
              <Card className="bg-white shadow-sm">
                <div className="grid gap-6 md:grid-cols-[1.15fr_0.85fr]">
                  <div className="space-y-6">
                    <h3 className="text-lg font-medium text-gray-900">Queues</h3>

                    <div className="space-y-6">
                      {queueOrder.map((queue, index) => {
                        const queueValue = Number(state.queues[queue] ?? 0);
                        const capacityValue = Number(state.capacities?.[queue] ?? 0);
                        const fill = getQueueFill(queueValue, capacityValue);
                        const shouldHighlight =
                          queue === highestLoadQueue && fill > 0.6;

                        return (
                          <div
                            key={queue}
                            className={`rounded-lg px-3 py-4 transition hover:bg-gray-50 ${
                              index % 2 === 0 ? "bg-gray-50" : "bg-white"
                            } ${shouldHighlight ? "ring-1 ring-red-300" : ""}`}
                          >
                            <div className="flex items-center justify-between">
                              <div>
                                <p className="text-sm font-medium text-gray-900">Queue {queue}</p>
                                <p className="text-sm text-gray-500">
                                  Capacity {formatNumber(capacityValue, 0)}
                                </p>
                              </div>
                              <p className="text-xl font-semibold text-gray-900">
                                {formatNumber(queueValue, 1)}
                              </p>
                            </div>

                            <div className="mt-2 space-y-2">
                              <p className="text-xs text-gray-500">Load</p>
                              <div className="h-3 w-full rounded-full bg-gray-200">
                                <div
                                  className={`h-3 rounded-full transition-all duration-500 ${getQueueBarClassName(fill)}`}
                                  style={{ width: `${fill * 100}%` }}
                                />
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>

                  <div className="space-y-6">
                    <h3 className="text-lg font-medium text-gray-900">Signals</h3>

                    <div className="rounded-lg bg-gray-50 p-3">
                      {signalRows.map((signal) => (
                        <div
                          key={signal.label}
                          className="border-b border-gray-100 py-2 last:border-b-0"
                        >
                          <div className="flex items-center justify-between gap-4">
                            <p className="text-sm text-gray-900">{signal.label}</p>
                            <p
                              className={`text-base font-medium ${
                                signal.label === "Retry rate"
                                  ? "text-blue-600"
                                  : signal.label === "Error rate"
                                    ? "text-red-500"
                                    : "text-gray-700"
                              }`}
                            >
                              {signal.value}
                            </p>
                          </div>
                          <p className="mt-1 text-xs text-gray-500">{signal.explanation}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </Card>
            </div>
          </Section>
        </div>
      </div>
    </PageContainer>
  );
}
