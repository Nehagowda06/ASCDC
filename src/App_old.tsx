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
} from "./lib/api";
import {
  EMPTY_STATE,
  type AgentAction,
  type EnvironmentState,
  type RecommendationResponse,
  type TaskMap,
  type TrajectoryStep,
} from "./lib/types";

export type PageId = "dashboard" | "simulation" | "analysis" | "baselines";

const navigationItems: Array<{ id: PageId; label: string }> = [
  { id: "dashboard", label: "Dashboard" },
  { id: "simulation", label: "Simulation" },
  { id: "analysis", label: "Analysis" },
  { id: "baselines", label: "Baselines" },
];

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

export default function App() {
  const [activePage, setActivePage] = useState<PageId>("dashboard");
  const [systemState, setSystemState] = useState<EnvironmentState>(EMPTY_STATE);
  const [tasks, setTasks] = useState<TaskMap>({});
  const [selectedTask, setSelectedTask] = useState<string | null>(null);
  const [recommendation, setRecommendation] = useState<RecommendationResponse | null>(null);
  const [trajectory, setTrajectory] = useState<TrajectoryStep[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function bootstrap() {
      try {
        const [nextState, nextTasks] = await Promise.all([getState(), fetchTasks()]);
        if (cancelled) {
          return;
        }

        setSystemState(nextState);
        setTasks(nextTasks);
        setSelectedTask(Object.keys(nextTasks)[0] ?? null);

        const nextRecommendation = await fetchRecommendation(nextState);
        if (!cancelled) {
          setRecommendation(nextRecommendation);
          setError(null);
        }
      } catch (nextError) {
        if (!cancelled) {
          setError(nextError instanceof Error ? nextError.message : "Unable to load dashboard.");
        }
      }
    }

    void bootstrap();

    return () => {
      cancelled = true;
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
      const [nextState, nextRecommendation] = await Promise.all([
        getState(),
        fetchRecommendation(nextObservation),
      ]);

      setSystemState(nextState);
      setRecommendation(nextRecommendation);
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
      const nextState = await getState();
      const nextRecommendation = await fetchRecommendation();

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
      const newState = await getState();
      const newRecommendation = await fetchRecommendation();

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
      setError(null);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Error applying recommendation.");
    } finally {
      setLoading(false);
    }
  }

  async function handleRefreshRecommendation() {
    setLoading(true);
    try {
      await refreshRecommendation(systemState);
      setError(null);
    } catch (nextError) {
      setError(nextError instanceof Error ? nextError.message : "Unable to refresh recommendation.");
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
          queueA: Number(stepItem.next_observation.queues.A ?? 0),
          queueB: Number(stepItem.next_observation.queues.B ?? 0),
          queueC: Number(stepItem.next_observation.queues.C ?? 0),
          action: formatActionLabel(stepItem.action),
          delayedEffects,
        };
      }),
    ];
  }, [systemState, trajectory]);

  const status = useMemo(
    () => getSystemStatus(systemState.system_pressure, systemState.failure_flags),
    [systemState.failure_flags, systemState.system_pressure],
  );

  const pageRegistry: Record<PageId, JSX.Element> = {
    dashboard: (
      <DecisionDashboardPage
        recommendation={recommendation}
        metrics={metrics}
        timeline={timeline}
        loading={loading}
        onApplyRecommendation={() => void handleUseRecommendation()}
        onRefreshRecommendation={() => void handleRefreshRecommendation()}
      />
    ),
    simulation: (
      <DecisionSimulationPage
        observation={systemState}
        tasks={tasks}
        selectedTask={selectedTask}
        loading={loading}
        recommendation={recommendation}
        onReset={(taskId) => void handleReset(taskId)}
        onManualStep={(action) => void handleStep(action)}
        onApplyRecommendation={() => void handleUseRecommendation()}
      />
    ),
    analysis: (
      <DecisionAnalysisPage
        recommendation={recommendation}
        loading={loading}
        onRefreshRecommendation={() => void handleRefreshRecommendation()}
      />
    ),
    baselines: <BaselinesPage />,
  };

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
        <div className="rounded-2xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600 shadow-sm">
          {error}
        </div>
      ) : null}
      <div key={activePage}>{pageRegistry[activePage]}</div>
    </Layout>
  );
}
