import { useEffect, useMemo, useState } from "react";

import { Layout } from "./components/Layout";
import { AgentComparisonPage } from "./pages/AgentComparisonPage";
import { BaselinesPage } from "./pages/BaselinesPage";
import { DecisionAnalysisPage } from "./pages/DecisionAnalysisPage";
import { DecisionDashboardPage } from "./pages/DecisionDashboardPage";
import { DecisionSimulationPage } from "./pages/DecisionSimulationPage";
import { SystemLogsPage } from "./pages/SystemLogsPage";
import type { TimelinePoint } from "./components/decision/Timeline";
import { computeDecisionMetrics, formatActionLabel, getSystemStatus } from "./lib/decision";
import {
  fetchTasks,
  getState,
  getAutoStatus,
  getSystemLogs,
  recommend as fetchRecommendation,
  reset,
  startAutoRunner,
  step,
  stopAutoRunner,
  getAgents,
  switchAgent,
  getSimpleMetrics,
  resetSimpleMetrics,
} from "./lib/api";
import {
  EMPTY_STATE,
  type AutoRunnerStatus,
  type AgentAction,
  type EnvironmentState,
  type RecommendationResponse,
  type SystemLogEntry,
  type TaskMap,
  type TrajectoryStep,
} from "./lib/types";

export type PageId = "dashboard" | "simulation" | "analysis" | "baselines" | "comparison" | "agents" | "logs";

const DEFAULT_PAGE: PageId = "dashboard";
const PAGE_STORAGE_KEY = "ascdc-active-page";

const navigationItems: Array<{ id: PageId; label: string }> = [
  { id: "dashboard", label: "Dashboard" },
  { id: "simulation", label: "Simulation" },
  { id: "analysis", label: "Analysis" },
  { id: "baselines", label: "Baselines" },
  { id: "agents", label: "Agents" },
  { id: "logs", label: "System Logs" },
];

function isPageId(value: string | null | undefined): value is PageId {
  return value === "comparison" || navigationItems.some((item) => item.id === value);
}

function getPageFromHash(hash: string) {
  const normalized = hash.replace(/^#\/?/, "");
  return isPageId(normalized) ? normalized : null;
}

function getInitialPage(): PageId {
  if (typeof window === "undefined") {
    return DEFAULT_PAGE;
  }

  const hashPage = getPageFromHash(window.location.hash);
  if (hashPage) {
    return hashPage;
  }

  const storedPage = window.localStorage.getItem(PAGE_STORAGE_KEY);
  return isPageId(storedPage) ? storedPage : DEFAULT_PAGE;
}

function normalizeStepAction(action?: Partial<AgentAction> | null): AgentAction {
  const actionType = (action?.type ?? action?.action_type ?? "noop").toLowerCase();

  if (actionType === "noop") {
    return {
      type: "noop",
      action_type: "noop",
      target: null,
    };
  }

  return {
    type: actionType,
    action_type: actionType,
    target: action?.target ?? null,
    amount: action?.amount ?? 1,
  };
}

function snapshotObservation(state: EnvironmentState) {
  return {
    queues: { ...state.queues },
    capacities: { ...state.capacities },
    latencies: { ...state.latencies },
    latency: state.latency,
    retry_rate: state.retry_rate,
    error_rate: state.error_rate,
    remaining_budget: state.remaining_budget,
    budget: state.budget,
    system_pressure: state.system_pressure,
    pending_actions: [...(state.pending_actions ?? [])],
    timestep: state.timestep,
    done: state.done,
  };
}

function formatLoadError(label: string, error: unknown) {
  const detail = error instanceof Error ? error.message : `Unable to load ${label}.`;
  return `${label}: ${detail}`;
}

function buildTimelinePoint(
  state: Partial<EnvironmentState>,
  actionLabel = "AUTO",
  delayedEffects = "",
): TimelinePoint {
  return {
    step: state.timestep ?? 0,
    queueA: Number(state.queues?.A ?? 0),
    queueB: Number(state.queues?.B ?? 0),
    queueC: Number(state.queues?.C ?? 0),
    action: actionLabel,
    delayedEffects,
  };
}

function appendTimelinePoint(
  current: TimelinePoint[],
  point: TimelinePoint,
  limit = 100,
): TimelinePoint[] {
  if (current.length === 0) {
    return [point];
  }

  const lastPoint = current[current.length - 1];
  if (lastPoint.step === point.step) {
    return [...current.slice(0, -1), point];
  }

  return [...current.slice(-(limit - 1)), point];
}

export default function App() {
  const [activePage, setActivePage] = useState<PageId>(getInitialPage);
  const [systemState, setSystemState] = useState<EnvironmentState>(EMPTY_STATE);
  const [tasks, setTasks] = useState<TaskMap>({});
  const [selectedTask, setSelectedTask] = useState<string | null>(null);
  const [recommendation, setRecommendation] = useState<RecommendationResponse | null>(null);
  const [trajectory, setTrajectory] = useState<TrajectoryStep[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [agents, setAgents] = useState<{ available: string[]; current: string }>({ available: [], current: "unknown" });
  const [simpleMetrics, setSimpleMetrics] = useState<any>({});
  const [autoStatus, setAutoStatus] = useState<AutoRunnerStatus>({ running: false });
  const [systemLogs, setSystemLogs] = useState<SystemLogEntry[]>([]);
  const [logsLoading, setLogsLoading] = useState(false);
  const [logsError, setLogsError] = useState<string | null>(null);
  const [timelinePoints, setTimelinePoints] = useState<TimelinePoint[]>([
    buildTimelinePoint(EMPTY_STATE, "START", ""),
  ]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    window.localStorage.setItem(PAGE_STORAGE_KEY, activePage);
    const nextHash = `#/${activePage}`;
    if (window.location.hash !== nextHash) {
      window.history.replaceState(null, "", nextHash);
    }
  }, [activePage]);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    const handleHashChange = () => {
      const nextPage = getPageFromHash(window.location.hash);
      if (nextPage) {
        setActivePage(nextPage);
      }
    };

    window.addEventListener("hashchange", handleHashChange);
    return () => window.removeEventListener("hashchange", handleHashChange);
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      const failures: string[] = [];
      const [nextStateResult, nextTasksResult, nextAgentsResult, nextMetricsResult] = await Promise.allSettled([
        getState(),
        fetchTasks(),
        getAgents(),
        getSimpleMetrics(),
      ]);

      if (cancelled) {
        return;
      }

      if (nextStateResult.status === "fulfilled") {
        setSystemState(nextStateResult.value);
        setTimelinePoints([
          buildTimelinePoint(nextStateResult.value, "START", ""),
        ]);
      } else {
        failures.push(formatLoadError("State", nextStateResult.reason));
      }

      if (nextTasksResult.status === "fulfilled") {
        setTasks(nextTasksResult.value);
        setSelectedTask((current) => {
          if (current && current in nextTasksResult.value) {
            return current;
          }

          return Object.keys(nextTasksResult.value)[0] ?? null;
        });
      } else {
        failures.push(formatLoadError("Tasks", nextTasksResult.reason));
      }

      if (nextAgentsResult.status === "fulfilled") {
        setAgents(nextAgentsResult.value);
      } else {
        failures.push(formatLoadError("Agents", nextAgentsResult.reason));
      }

      if (nextMetricsResult.status === "fulfilled") {
        setSimpleMetrics(nextMetricsResult.value);
      } else {
        failures.push(formatLoadError("Metrics", nextMetricsResult.reason));
      }

      try {
        const [nextRecommendation, nextAutoStatus] = await Promise.all([
          nextStateResult.status === "fulfilled"
            ? fetchRecommendation(nextStateResult.value)
            : fetchRecommendation(),
          getAutoStatus(),
        ]);

        if (!cancelled) {
          setRecommendation(nextRecommendation);
          setAutoStatus(nextAutoStatus);
        }
      } catch (nextError) {
        if (!cancelled) {
          failures.push(formatLoadError("Recommendation", nextError));
          setRecommendation(null);
        }
      }

      if (!cancelled) {
        setError(failures.length > 0 ? failures.join(" | ") : null);
      }
    }

    void bootstrap();

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function updateMetrics() {
      try {
        if (!cancelled) {
          const metrics = await getSimpleMetrics();
          setSimpleMetrics(metrics);
        }
      } catch (e) {
        console.error("Failed to update metrics:", e);
      }
    }

    // Update metrics every 2 seconds
    const interval = setInterval(updateMetrics, 2000);

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    if (!autoStatus.running) {
      return;
    }

    async function refreshAutoState() {
      try {
        const [nextStatus, nextMetrics] = await Promise.all([
          getAutoStatus(),
          getSimpleMetrics(),
        ]);

        if (cancelled) {
          return;
        }

        setAutoStatus(nextStatus);
        if (nextStatus.state) {
          setSystemState(nextStatus.state);
          try {
            const nextRecommendation = await fetchRecommendation(nextStatus.state);
            if (!cancelled) {
              setRecommendation(nextRecommendation);
            }
          } catch (nextError) {
            if (!cancelled) {
              setRecommendation(null);
            }
          }
        }
        setSimpleMetrics(nextMetrics);
      } catch (nextError) {
        if (!cancelled) {
          setError(nextError instanceof Error ? nextError.message : "Unable to refresh auto mode.");
          setAutoStatus((current) => ({ ...current, running: false }));
        }
      }
    }

    void refreshAutoState();
    const timer = window.setInterval(() => {
      void refreshAutoState();
    }, 800);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [autoStatus.running]);

  useEffect(() => {
    let cancelled = false;

    if (!autoStatus.running) {
      return;
    }

    async function refreshAutoTimeline() {
      try {
        const nextState = await getState();
        if (cancelled) {
          return;
        }

        setSystemState(nextState);
        setTimelinePoints((current) =>
          appendTimelinePoint(
            current,
            buildTimelinePoint(
              nextState,
              autoStatus.last_action ? formatActionLabel(autoStatus.last_action) : "AUTO",
              (nextState.pending_actions ?? [])
                .map((item) => `${item.type.toUpperCase()} ${item.target ?? "System"} @ ${item.applies_at}`)
                .join(" | "),
            ),
          ),
        );
      } catch (nextError) {
        if (!cancelled) {
          setError(nextError instanceof Error ? nextError.message : "Unable to refresh auto timeline.");
        }
      }
    }

    void refreshAutoTimeline();
    const interval = window.setInterval(() => {
      void refreshAutoTimeline();
    }, 500);

    return () => {
      cancelled = true;
      window.clearInterval(interval);
    };
  }, [autoStatus.running, autoStatus.last_action]);

  useEffect(() => {
    let cancelled = false;

    if (activePage !== "logs") {
      return;
    }

    async function refreshLogs() {
      setLogsLoading(true);
      try {
        const nextLogs = await getSystemLogs();
        if (!cancelled) {
          setSystemLogs(nextLogs);
          setLogsError(null);
        }
      } catch (nextError) {
        if (!cancelled) {
          setLogsError(nextError instanceof Error ? nextError.message : "Unable to load logs.");
        }
      } finally {
        if (!cancelled) {
          setLogsLoading(false);
        }
      }
    }

    void refreshLogs();
    const timer = window.setInterval(() => {
      void refreshLogs();
    }, 1000);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [activePage]);

  async function refreshRecommendation(snapshot?: Partial<EnvironmentState>) {
    setLoading(true);
    try {
      const nextState = snapshot ? { ...systemState, ...snapshot } : await getState();
      const [nextRecommendation, nextMetrics, nextAgents, nextAutoStatus] = await Promise.all([
        fetchRecommendation(nextState),
        getSimpleMetrics(),
        getAgents(),
        getAutoStatus(),
      ]);

      setSystemState(nextState);
      setRecommendation(nextRecommendation);
      setSimpleMetrics(nextMetrics);
      setAgents(nextAgents);
      setAutoStatus(nextAutoStatus);
      setError(null);
    } catch (nextError) {
      const message = nextError instanceof Error ? nextError.message : "Unknown error";
      setError(`Unable to refresh analysis: ${message}`);
    } finally {
      setLoading(false);
    }
  }

  async function handleReset(taskId?: string) {
    setLoading(true);
    try {
      const nextObservation = await reset(taskId);
      const [nextState, nextRecommendation, nextMetrics] = await Promise.all([
        getState(),
        fetchRecommendation(nextObservation),
        getSimpleMetrics()
      ]);

      setSystemState(nextState);
      setTimelinePoints([
        buildTimelinePoint(nextState, "START", ""),
      ]);
      setRecommendation(nextRecommendation);
      setSimpleMetrics(nextMetrics);
      setTrajectory([]);
      setSelectedTask(taskId ?? selectedTask);
      setError(null);
    } catch (nextError) {
      const message = nextError instanceof Error ? nextError.message : "Unknown error";
      setError(`Unable to reset environment: ${message}`);
    } finally {
      setLoading(false);
    }
  }

  async function applyAction(action: AgentAction) {
    setLoading(true);
    try {
      const previousObservation = snapshotObservation(systemState);
      const normalizedAction = normalizeStepAction(action);
      const response = await step(normalizedAction);
      const [nextState, nextRecommendation, nextMetrics] = await Promise.all([
        getState(),
        fetchRecommendation(),
        getSimpleMetrics()
      ]);

      setTrajectory((current) => [
        ...current,
        {
          timestep: response.observation.timestep ?? current.length + 1,
          observation: previousObservation,
          action: normalizedAction,
          reward: response.reward,
          next_observation: response.observation,
          done: response.done,
          info: response.info,
        },
      ]);
      setSystemState({ ...nextState });
      setTimelinePoints((current) =>
        appendTimelinePoint(
          current,
          buildTimelinePoint(
            nextState,
            formatActionLabel(normalizedAction),
            (response.observation.pending_actions ?? [])
              .map((item) => `${item.type.toUpperCase()} ${item.target ?? "System"} @ ${item.applies_at}`)
              .join(" | "),
          ),
        ),
      );
      setRecommendation({ ...nextRecommendation });
      setSimpleMetrics(nextMetrics);
      setError(null);
    } catch (nextError) {
      const message = nextError instanceof Error ? nextError.message : "Unknown error";
      setError(`Unable to step environment: ${message}`);
    } finally {
      setLoading(false);
    }
  }

  async function handleStep(action: AgentAction) {
    await applyAction(action);
  }

  async function handleUseRecommendation() {
    if (!recommendation) {
      return;
    }

    await applyAction(recommendation.action);
  }

  async function handleSwitchAgent(agentName: string) {
    setLoading(true);
    try {
      await switchAgent(agentName);
      const [nextAgents, nextRecommendation, nextMetrics] = await Promise.all([
        getAgents(),
        fetchRecommendation(),
        getSimpleMetrics()
      ]);
      
      setAgents(nextAgents);
      setRecommendation(nextRecommendation);
      setSimpleMetrics(nextMetrics);
      setError(null);
    } catch (nextError) {
      const message = nextError instanceof Error ? nextError.message : "Unknown error";
      setError(`Failed to switch agent: ${message}`);
    } finally {
      setLoading(false);
    }
  }

  async function handleResetMetrics() {
    setLoading(true);
    try {
      await resetSimpleMetrics();
      const nextMetrics = await getSimpleMetrics();
      setSimpleMetrics(nextMetrics);
      setError(null);
    } catch (nextError) {
      const message = nextError instanceof Error ? nextError.message : "Unknown error";
      setError(`Failed to reset metrics: ${message}`);
    } finally {
      setLoading(false);
    }
  }

  const metrics = useMemo(() => computeDecisionMetrics(trajectory), [trajectory]);

  async function handleStartAuto() {
    setLoading(true);
    try {
      const nextStatus = await startAutoRunner({
        interval: 0.5,
        task_id: selectedTask,
      });
      setAutoStatus(nextStatus);
      const nextAutoState = nextStatus.state;
      if (nextAutoState) {
        setSystemState(nextAutoState);
        setTimelinePoints([
          buildTimelinePoint(nextAutoState, "AUTO START", ""),
        ]);
      }
      setTrajectory([]);
      const [nextRecommendation, nextMetrics] = await Promise.all([
        nextAutoState ? fetchRecommendation(nextAutoState) : fetchRecommendation(),
        getSimpleMetrics(),
      ]);
      setRecommendation(nextRecommendation);
      setSimpleMetrics(nextMetrics);
      setError(null);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Unable to start auto mode.");
    } finally {
      setLoading(false);
    }
  }

  async function handleStopAuto() {
    setLoading(true);
    try {
      const nextStatus = await stopAutoRunner();
      setAutoStatus(nextStatus);
      const nextAutoState = nextStatus.state;
      if (nextAutoState) {
        setSystemState(nextAutoState);
        setTimelinePoints((current) =>
          appendTimelinePoint(
            current,
            buildTimelinePoint(
              nextAutoState,
              "AUTO STOP",
              (nextAutoState.pending_actions ?? [])
                .map((item) => `${item.type.toUpperCase()} ${item.target ?? "System"} @ ${item.applies_at}`)
                .join(" | "),
            ),
          ),
        );
      }
      const [nextRecommendation, nextMetrics] = await Promise.all([
        nextAutoState ? fetchRecommendation(nextAutoState) : fetchRecommendation(),
        getSimpleMetrics(),
      ]);
      setRecommendation(nextRecommendation);
      setSimpleMetrics(nextMetrics);
      setError(null);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Unable to stop auto mode.");
    } finally {
      setLoading(false);
    }
  }

  const timeline = useMemo(() => timelinePoints, [timelinePoints]);

  // Convert simpleMetrics to DecisionMetrics format
  const dashboardMetrics = useMemo(() => ({
    totalReward: simpleMetrics.total_reward || 0,
    necessaryActionRatio: simpleMetrics.necessary_action_ratio || 0,
    averageImpact: simpleMetrics.average_impact || 0,
    positiveImpactRate: simpleMetrics.positive_impact_rate || 0
  }), [simpleMetrics]);

  const status = getSystemStatus(systemState.system_pressure, systemState.failure_flags);

  return (
    <Layout
      activePage={activePage === "comparison" ? "baselines" : activePage}
      items={navigationItems}
      onNavigate={setActivePage}
      statusLabel={status.label}
      statusDotClassName={status.dotClassName}
      statusPillClassName={status.pillClassName}
      timestep={systemState.timestep ?? 0}
    >
      {error ? (
        <div className="rounded-xl border border-red-900/40 bg-red-500/10 px-4 py-3 text-sm text-red-300 shadow-sm">
          {error}
        </div>
      ) : null}

      {activePage === "dashboard" && (
        <DecisionDashboardPage
          recommendation={recommendation}
          metrics={dashboardMetrics}
          timeline={timeline}
          loading={loading}
          onApplyRecommendation={handleUseRecommendation}
          onRefreshRecommendation={refreshRecommendation}
        />
      )}

      {activePage === "simulation" && (
        <DecisionSimulationPage
          observation={systemState}
          tasks={tasks}
          selectedTask={selectedTask}
          loading={loading}
          autoStatus={autoStatus}
          recommendation={recommendation}
          onReset={handleReset}
          onManualStep={handleStep}
          onApplyRecommendation={handleUseRecommendation}
          onStartAuto={handleStartAuto}
          onStopAuto={handleStopAuto}
        />
      )}

      {activePage === "analysis" && (
        <DecisionAnalysisPage
          recommendation={recommendation}
          loading={loading}
          onRefreshRecommendation={refreshRecommendation}
        />
      )}

      {activePage === "baselines" && (
        <BaselinesPage onOpenComparison={() => setActivePage("comparison")} />
      )}

      {activePage === "comparison" && (
        <AgentComparisonPage onBackToTable={() => setActivePage("baselines")} />
      )}

      {activePage === "agents" && (
        <AgentsPage
          agents={agents}
          onSwitchAgent={handleSwitchAgent}
          onResetMetrics={handleResetMetrics}
          loading={loading}
          simpleMetrics={simpleMetrics}
        />
      )}

      {activePage === "logs" && (
        <SystemLogsPage
          logs={systemLogs}
          loading={logsLoading}
          error={logsError}
        />
      )}
    </Layout>
  );
}

function AgentsPage({
  agents,
  onSwitchAgent,
  onResetMetrics,
  loading,
  simpleMetrics,
}: {
  agents: { available: string[]; current: string };
  onSwitchAgent: (agentName: string) => Promise<void>;
  onResetMetrics: () => Promise<void>;
  loading: boolean;
  simpleMetrics: any;
}) {
  const agentDetails: Record<string, string[]> = {
    "simple-adaptive": [
      "Balances action and restraint based on current pressure and queue ratios.",
      "Prioritizes the most stressed queue before spreading interventions.",
      "Escalates from scale to restart only when pressure becomes clearly critical.",
    ],
    "simple-conservative": [
      "Waits longer before acting and intervenes mainly during high-pressure states.",
      "Prefers fewer actions to preserve budget and avoid unnecessary disruption.",
      "Best suited for stable periods where overreaction is more costly than delay.",
    ],
    "simple-aggressive": [
      "Responds early to imbalances and treats moderate drift as worth correcting.",
      "Prefers fast intervention to prevent delayed instability from compounding.",
      "Useful when small warning signs tend to turn into larger incidents quickly.",
    ],
    "simple-learning": [
      "Learns from previous rewards and updates a compact state-action value table.",
      "Uses the current pressure and bottleneck queue to pick previously rewarding actions.",
      "Improves over time as it collects more experience from live simulation steps.",
    ],
    "strong-decision": [
      "Simulates short rollout sequences before choosing the first action to take.",
      "Compares likely near-term outcomes instead of relying only on static thresholds.",
      "Favors stronger intervention under high pressure and avoids overreacting in calm states.",
    ],
  };

  const currentAgentDetails =
    agentDetails[agents.current] ?? [
      "Uses the shared environment evaluation loop to choose the next action.",
      "Participates in the same metrics and counterfactual analysis as other agents.",
      "Can be compared directly against the built-in strategies from this page.",
    ];

  return (
    <div className="px-1 py-1 text-gray-100">
      <div className="mx-auto max-w-7xl space-y-4">
        <div className="space-y-2">
          <div className="space-y-2">
            <h1>AI Agent Control</h1>
            <p className="max-w-3xl text-sm leading-6 text-gray-400">
              Switch between different AI agents to test their behavior and performance.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div className="overflow-hidden rounded-xl border border-[#242934] bg-[#14181f] shadow-sm">
            <div className="p-4">
              <h3 className="text-lg font-medium text-white">Current Agent</h3>
              <div className="mt-2 space-y-4">
                <p className="text-xl font-semibold text-[#C38EB4]">{agents.current}</p>
                <p className="text-sm leading-6 text-gray-400">Active agent</p>
                <div className="rounded-xl border border-[#2a3039] bg-[#171c24] px-4 py-4">
                  <p className="text-xs font-medium uppercase tracking-wide text-gray-500">
                    Agent Details
                  </p>
                  <div className="mt-3 space-y-3">
                    {currentAgentDetails.map((detail) => (
                      <div key={detail} className="flex items-start gap-3">
                        <span className="mt-1 h-2 w-2 rounded-full bg-[#C38EB4]" />
                        <p className="text-sm leading-6 text-gray-300">{detail}</p>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div className="overflow-hidden rounded-xl border border-[#242934] bg-[#14181f] shadow-sm">
            <div className="p-4">
              <h3 className="text-lg font-medium text-white">Available Agents</h3>
              <div className="mt-2 space-y-2">
                {agents.available.length === 0 ? (
                  <div className="rounded-lg border border-dashed border-[#2a3039] bg-[#171c24] p-4 text-sm text-gray-400">
                    No agents are available yet.
                  </div>
                ) : agents.available.map((agentName) => (
                  <div
                    key={agentName}
                    className="flex items-center justify-between rounded-lg border border-[#2a3039] bg-[#171c24] p-3 transition-colors hover:border-[#39404c]"
                  >
                    <div>
                      <p className="font-medium text-white">{agentName}</p>
                      <p className="text-sm text-gray-400">
                        {agentName.includes("adaptive") && "Adaptive strategy - responds to current conditions"}
                        {agentName.includes("strong") && "Strong decision strategy - evaluates rollout outcomes before acting"}
                        {agentName.includes("learning") && "Learning strategy - repeats historically rewarding actions"}
                        {agentName.includes("conservative") && "Conservative strategy - acts only in emergencies"}
                        {agentName.includes("aggressive") && "Aggressive strategy - acts on any imbalance"}
                      </p>
                    </div>
                    <button
                      onClick={() => onSwitchAgent(agentName)}
                      disabled={loading || agentName === agents.current}
                      className={`inline-flex items-center rounded-lg border px-3 py-2 text-sm font-medium shadow-sm transition-colors ${
                        agentName === agents.current
                          ? "cursor-not-allowed border-[#2b313b] bg-[#202631] text-gray-500"
                          : "border-[#C38EB4] bg-[#C38EB4] text-white hover:border-[#b47fa5] hover:bg-[#b47fa5]"
                      }`}
                    >
                      {agentName === agents.current ? "Active" : "Switch"}
                    </button>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        <div className="overflow-hidden rounded-xl border border-[#242934] bg-[#14181f] shadow-sm">
          <div className="p-4">
            <h3 className="text-lg font-medium text-white">Performance Metrics</h3>
            <div className="mt-2 grid grid-cols-2 gap-4 xl:grid-cols-5">
              <div className="text-center">
                <p className="text-xl font-semibold text-[#C38EB4]">{simpleMetrics.total_reward || 0}</p>
                <p className="text-xs uppercase tracking-wide text-gray-500">Total Reward</p>
              </div>
              <div className="text-center">
                <p className="text-xl font-semibold text-green-600">{Math.round((simpleMetrics.necessary_action_ratio || 0) * 100)}%</p>
                <p className="text-xs uppercase tracking-wide text-gray-500">Necessary Action Ratio</p>
              </div>
              <div className="text-center">
                <p className="text-xl font-semibold text-purple-600">{Math.round((simpleMetrics.positive_impact_rate || 0) * 100)}%</p>
                <p className="text-xs uppercase tracking-wide text-gray-500">Positive Impact Rate</p>
              </div>
              <div className="text-center">
                <p className="text-xl font-semibold text-cyan-600">{simpleMetrics.average_impact || 0}</p>
                <p className="text-xs uppercase tracking-wide text-gray-500">Avg Impact</p>
              </div>
              <div className="text-center">
                <p className="text-xl font-semibold text-[#C38EB4]">{simpleMetrics.total_actions || 0}</p>
                <p className="text-xs uppercase tracking-wide text-gray-500">Total Actions</p>
              </div>
            </div>
            <div className="mt-4">
              <button
                onClick={() => void onResetMetrics()}
                disabled={loading}
                className="flex w-full justify-center rounded-lg border border-red-600 bg-red-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition-colors hover:border-red-700 hover:bg-red-700"
              >
                {loading ? "Resetting..." : "Reset Metrics"}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
