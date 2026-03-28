import type {
  AgentAction,
  BaselineResults,
  EnvironmentState,
  Observation,
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

export function fetchState() {
  return request<EnvironmentState>("/state");
}

export function resetEnvironment(taskId?: string) {
  const query = taskId ? `?task_id=${encodeURIComponent(taskId)}` : "";
  return request<Observation>(`/reset${query}`, {
    method: "POST",
  });
}

export function stepEnvironment(action: AgentAction) {
  return request<StepResponse>("/step", {
    method: "POST",
    body: JSON.stringify(action),
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
