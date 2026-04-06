import type {
  AgentAction,
  BaselineResults,
  EnvironmentState,
  Observation,
  RecommendationResponse,
  StepResponse,
  TaskMap,
  TrajectoryStep,
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    const detail =
      payload && typeof payload === "object" && "detail" in payload
        ? String(payload.detail)
        : `Request failed with status ${response.status}`;
    throw new Error(detail);
  }

  return response.json() as Promise<T>;
}

function normalizeAction(action: AgentAction) {
  const actionType = (action.action_type ?? action.type ?? "noop").toLowerCase();

  if (actionType === "noop") {
    return {
      type: "noop",
      target: null,
    };
  }

  return {
    ...action,
    type: actionType,
    action_type: actionType,
    target: action.target ?? null,
  };
}

export function getState() {
  return request<EnvironmentState>("/state");
}

export function fetchState() {
  return getState();
}

export function reset(taskId?: string) {
  const query = taskId ? `?task_id=${encodeURIComponent(taskId)}` : "";
  return request<Observation>(`/reset${query}`, {
    method: "POST",
  });
}

export function resetEnvironment(taskId?: string) {
  return reset(taskId);
}

export function step(action: AgentAction) {
  return request<StepResponse>("/step", {
    method: "POST",
    body: JSON.stringify(normalizeAction(action)),
  });
}

export function stepEnvironment(action: AgentAction) {
  return step(action);
}

export function recommend(currentState?: Partial<EnvironmentState> | Partial<Observation>) {
  return request<RecommendationResponse>("/recommend", {
    method: "POST",
    body: JSON.stringify(currentState ?? {}),
  });
}

export function fetchTasks() {
  return request<TaskMap>("/tasks");
}

export function runBaselines() {
  return request<BaselineResults>("/baseline", {
    method: "POST",
  });
}

export function gradeTrajectory(trajectory: TrajectoryStep[]) {
  return request<{ score: number }>("/grader", {
    method: "POST",
    body: JSON.stringify(trajectory),
  });
}
