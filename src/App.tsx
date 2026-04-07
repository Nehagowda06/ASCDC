import { useEffect, useMemo, useState } from "react";

import { Layout } from "./components/Layout";
import { BaselinesPage } from "./pages/BaselinesPage";
import { DecisionAnalysisPage } from "./pages/DecisionAnalysisPage";
import { DecisionDashboardPage } from "./pages/DecisionDashboardPage";
import { DecisionSimulationPage } from "./pages/DecisionSimulationPage";
import { computeDecisionMetrics, formatActionLabel, getSystemStatus } from "./lib/decision";
import {
  fetchTasks,
  getState,
  recommend as fetchRecommendation,
  reset,
  step,
  getAgents,
  switchAgent,
  getSimpleMetrics,
  resetSimpleMetrics,
} from "./lib/api";
import {
  EMPTY_STATE,
  type AgentAction,
  type EnvironmentState,
  type RecommendationResponse,
  type TaskMap,
  type TrajectoryStep,
} from "./lib/types";

export type PageId = "dashboard" | "simulation" | "analysis" | "baselines" | "agents";

const DEFAULT_PAGE: PageId = "dashboard";
const PAGE_STORAGE_KEY = "ascdc-active-page";

const navigationItems: Array<{ id: PageId; label: string }> = [
  { id: "dashboard", label: "Dashboard" },
  { id: "simulation", label: "Simulation" },
  { id: "analysis", label: "Analysis" },
  { id: "baselines", label: "Baselines" },
  { id: "agents", label: "Agents" },
];

function isPageId(value: string | null | undefined): value is PageId {
  return navigationItems.some((item) => item.id === value);
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
        const nextRecommendation =
          nextStateResult.status === "fulfilled"
            ? await fetchRecommendation(nextStateResult.value)
            : await fetchRecommendation();

        if (!cancelled) {
          setRecommendation(nextRecommendation);
        }
      } catch (nextError) {
        if (!cancelled) {
          failures.push(formatLoadError("Recommendation", nextError));
          setRecommendation(null);
        }
      }

      if (!cancelled) {
        setError(failures.length > 0 ? failures.join(" ") : null);
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

  async function refreshRecommendation(snapshot?: Partial<EnvironmentState>) {
    const nextRecommendation = await fetchRecommendation(snapshot ?? systemState);
    setRecommendation(nextRecommendation);
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
      setRecommendation(nextRecommendation);
      setSimpleMetrics(nextMetrics);
      setTrajectory([]);
      setSelectedTask(taskId ?? selectedTask);
      setError(null);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Unable to reset environment.");
    } finally {
      setLoading(false);
    }
  }

  async function handleStep(action: AgentAction) {
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
      setRecommendation({ ...nextRecommendation });
      setSimpleMetrics(nextMetrics);
      setError(null);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Unable to step environment.");
    } finally {
      setLoading(false);
    }
  }

  async function handleUseRecommendation() {
    if (!recommendation) {
      return;
    }

    setLoading(true);
    try {
      const previousObservation = snapshotObservation(systemState);
      const recommendedAction = normalizeStepAction(recommendation.action);

      const response = await step(recommendedAction);
      const [newState, newRecommendation, newMetrics] = await Promise.all([
        getState(),
        fetchRecommendation(),
        getSimpleMetrics()
      ]);

      setTrajectory((current) => [
        ...current,
        {
          timestep: response.observation.timestep ?? current.length + 1,
          observation: previousObservation,
          action: recommendedAction,
          reward: response.reward,
          next_observation: response.observation,
          done: response.done,
          info: response.info,
        },
      ]);
      setSystemState({ ...newState });
      setRecommendation({ ...newRecommendation });
      setSimpleMetrics(newMetrics);
      setError(null);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Error applying recommendation.");
    } finally {
      setLoading(false);
    }
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
      setError(nextError instanceof Error ? nextError.message : "Failed to switch agent.");
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
      setError(nextError instanceof Error ? nextError.message : "Failed to reset metrics.");
    } finally {
      setLoading(false);
    }
  }

  const metrics = useMemo(() => computeDecisionMetrics(trajectory), [trajectory]);

  const timeline = useMemo(() => {
    if (trajectory.length === 0) {
      return [
        {
          step: systemState.timestep ?? 0,
          queueA: Number(systemState.queues.A ?? 0),
          queueB: Number(systemState.queues.B ?? 0),
          queueC: Number(systemState.queues.C ?? 0),
          action: "START",
          delayedEffects: "",
        },
      ];
    }

    const firstObservation = trajectory[0].observation;
    return [
      {
        step: firstObservation.timestep ?? 0,
        queueA: Number(firstObservation.queues.A ?? 0),
        queueB: Number(firstObservation.queues.B ?? 0),
        queueC: Number(firstObservation.queues.C ?? 0),
        action: "START",
        delayedEffects: "",
      },
      ...trajectory.map((stepItem) => {
        const delayedEffects = (stepItem.next_observation.pending_actions ?? [])
          .map((item) => `${item.type.toUpperCase()} ${item.target ?? "System"} @ ${item.applies_at}`)
          .join(" | ");

        return {
          step: stepItem.timestep,
          queueA: Number(stepItem.observation.queues.A ?? 0),
          queueB: Number(stepItem.observation.queues.B ?? 0),
          queueC: Number(stepItem.observation.queues.C ?? 0),
          action: formatActionLabel(stepItem.action),
          delayedEffects,
        };
      }),
    ];
  }, [systemState, trajectory]);

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
      activePage={activePage}
      items={navigationItems}
      onNavigate={setActivePage}
      statusLabel={status.label}
      statusDotClassName={status.dotClassName}
      statusPillClassName={status.pillClassName}
      timestep={systemState.timestep ?? 0}
    >
      {error ? (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 shadow-sm">
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
          recommendation={recommendation}
          onReset={handleReset}
          onManualStep={handleStep}
          onApplyRecommendation={handleUseRecommendation}
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
        <BaselinesPage />
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
  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 px-6 py-6 text-gray-900">
      <div className="mx-auto max-w-7xl space-y-8">
        <div className="space-y-2">
          <div className="inline-flex items-center rounded-full border border-gray-200 bg-white px-3 py-1 text-xs font-medium uppercase tracking-[0.16em] text-gray-500 shadow-sm">
            Agent Management
          </div>
          <div className="space-y-2">
            <h1 className="text-3xl font-bold text-gray-900">AI Agent Control</h1>
            <p className="max-w-3xl text-sm leading-6 text-gray-600">
              Switch between different AI agents to test their behavior and performance.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="bg-white overflow-hidden shadow rounded-lg">
            <div className="px-4 py-5 sm:p-6">
              <h3 className="text-lg font-medium text-gray-900">Current Agent</h3>
              <div className="mt-2">
                <p className="text-2xl font-bold text-blue-600">{agents.current}</p>
                <p className="text-sm text-gray-500">Active agent</p>
              </div>
            </div>
          </div>

          <div className="bg-white overflow-hidden shadow rounded-lg">
            <div className="px-4 py-5 sm:p-6">
              <h3 className="text-lg font-medium text-gray-900">Available Agents</h3>
              <div className="mt-2 space-y-2">
                {agents.available.length === 0 ? (
                  <div className="rounded-lg border border-dashed border-gray-200 p-4 text-sm text-gray-500">
                    No agents are available yet.
                  </div>
                ) : agents.available.map((agentName) => (
                  <div key={agentName} className="flex items-center justify-between p-3 border rounded-lg hover:bg-gray-50">
                    <div>
                      <p className="font-medium text-gray-900">{agentName}</p>
                      <p className="text-sm text-gray-500">
                        {agentName.includes("adaptive") && "Adaptive strategy - responds to current conditions"}
                        {agentName.includes("conservative") && "Conservative strategy - acts only in emergencies"}
                        {agentName.includes("aggressive") && "Aggressive strategy - acts on any imbalance"}
                      </p>
                    </div>
                    <button
                      onClick={() => onSwitchAgent(agentName)}
                      disabled={loading || agentName === agents.current}
                      className={`inline-flex items-center px-3 py-2 border border-transparent text-sm leading-4 font-medium rounded-md shadow-sm focus:outline-none focus:ring-2 focus:ring-offset-2 ${
                        agentName === agents.current
                          ? "bg-gray-300 text-gray-500 cursor-not-allowed"
                          : "text-white bg-blue-600 hover:bg-blue-700 focus:ring-blue-500"
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

        <div className="bg-white overflow-hidden shadow rounded-lg">
          <div className="px-4 py-5 sm:p-6">
            <h3 className="text-lg font-medium text-gray-900">Performance Metrics</h3>
            <div className="mt-2 grid grid-cols-2 gap-4 xl:grid-cols-5">
              <div className="text-center">
                <p className="text-2xl font-bold text-blue-600">{simpleMetrics.total_reward || 0}</p>
                <p className="text-sm text-gray-500">Total Reward</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-bold text-green-600">{Math.round((simpleMetrics.necessary_action_ratio || 0) * 100)}%</p>
                <p className="text-sm text-gray-500">Necessary Action Ratio</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-bold text-purple-600">{Math.round((simpleMetrics.positive_impact_rate || 0) * 100)}%</p>
                <p className="text-sm text-gray-500">Positive Impact Rate</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-bold text-cyan-600">{simpleMetrics.average_impact || 0}</p>
                <p className="text-sm text-gray-500">Avg Impact</p>
              </div>
              <div className="text-center">
                <p className="text-2xl font-bold text-orange-600">{simpleMetrics.total_actions || 0}</p>
                <p className="text-sm text-gray-500">Total Actions</p>
              </div>
            </div>
            <div className="mt-4">
              <button
                onClick={() => void onResetMetrics()}
                disabled={loading}
                className="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-red-600 hover:bg-red-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500"
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
