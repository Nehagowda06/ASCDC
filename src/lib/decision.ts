import type {
  AgentAction,
  DecisionMetrics,
  FailureFlags,
  QueueMap,
  TrajectoryStep,
} from "./types";

export function formatActionLabel(action: Partial<AgentAction> | null | undefined) {
  const actionType = (action?.type ?? action?.action_type ?? "noop").toString().toUpperCase();
  const target = action?.target;

  return target ? `${actionType} ${target}` : actionType;
}

export function getSystemStatus(
  pressure: number | undefined,
  failureFlags?: FailureFlags,
) {
  if (failureFlags?.collapsed || (pressure ?? 0) >= 2) {
    return {
      label: "Critical",
      dotClassName: "bg-red-500",
      pillClassName: "border-red-200 bg-red-50 text-red-600",
    };
  }

  if ((pressure ?? 0) >= 1) {
    return {
      label: "Warning",
      dotClassName: "bg-amber-500",
      pillClassName: "border-amber-200 bg-amber-50 text-amber-600",
    };
  }

  return {
    label: "Stable",
    dotClassName: "bg-emerald-500",
    pillClassName: "border-emerald-200 bg-emerald-50 text-emerald-600",
  };
}

export function computeDecisionMetrics(trajectory: TrajectoryStep[]): DecisionMetrics {
  const totalReward = trajectory.reduce((sum, step) => sum + safeNumber(step.reward), 0);
  const evaluatedActions = trajectory.filter(
    (step) => (step.action.type ?? step.action.action_type ?? "noop") !== "noop",
  );

  if (evaluatedActions.length === 0) {
    return {
      totalReward,
      necessaryActionRatio: 0,
      averageImpact: 0,
      positiveImpactRate: 0,
    };
  }

  const impacts = evaluatedActions.map((step) => safeNumber(step.info.counterfactual_impact));
  const necessaryCount = evaluatedActions.filter(
    (step) => Boolean(step.info.was_action_necessary),
  ).length;
  const positiveCount = impacts.filter((impact) => impact > 0).length;
  const impactTotal = impacts.reduce((sum, impact) => sum + safeNumber(impact), 0);

  return {
    totalReward: safeNumber(totalReward),
    necessaryActionRatio: safeRatio(necessaryCount, evaluatedActions.length),
    averageImpact: safeRatio(impactTotal, impacts.length),
    positiveImpactRate: safeRatio(positiveCount, evaluatedActions.length),
  };
}

export function getQueueTrend(
  currentQueues: QueueMap | undefined,
  previousQueues: QueueMap | undefined,
) {
  if (!currentQueues || !previousQueues) {
    return "Cold start";
  }

  const delta = (currentQueues.B ?? 0) - (previousQueues.B ?? 0);
  if (delta > 0.5) {
    return "Queue B rising";
  }
  if (delta < -0.5) {
    return "Queue B easing";
  }
  return "Queues holding steady";
}

function safeNumber(value: unknown) {
  const numeric = Number(value ?? 0);
  return Number.isFinite(numeric) ? numeric : 0;
}

function safeRatio(numerator: number, denominator: number) {
  if (denominator <= 0) {
    return 0;
  }
  return safeNumber(numerator / denominator);
}
