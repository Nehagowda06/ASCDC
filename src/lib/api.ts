import type {
  AgentAction,
  AutoRunnerStatus,
  BaselineResults,
  EnvironmentState,
  Observation,
  RecommendationResponse,
  SystemLogEntry,
  StepResponse,
  TaskMap,
  TrajectoryStep,
} from "./types";

const API_BASE = import.meta.env.VITE_API_BASE?.trim();
let baselineResultsCache: BaselineResults | null = null;
let baselineResultsPromise: Promise<BaselineResults> | null = null;

function getApiBaseCandidates() {
  if (API_BASE) {
    return [API_BASE.replace(/\/+$/, "")];
  }

  if (typeof window === "undefined") {
    return ["http://localhost:8000"];
  }

  const { hostname, origin, port, protocol } = window.location;
  const candidates: string[] = [];
  const normalizedOrigin = origin.replace(/\/+$/, "");

  if (protocol.startsWith("http") && (port === "5173" || port === "4173")) {
    candidates.push(`${protocol}//${hostname}:8000`);
    candidates.push(normalizedOrigin);
  } else if (protocol.startsWith("http")) {
    candidates.push(normalizedOrigin);
    candidates.push(`${protocol}//${hostname}:8000`);
  } else {
    candidates.push("http://localhost:8000");
  }

  candidates.push("http://127.0.0.1:8000");
  candidates.push("http://localhost:8000");

  return [...new Set(candidates.map((candidate) => candidate.replace(/\/+$/, "")))];
}

async function parseError(response: Response) {
  const payload = await response.json().catch(() => null);

  if (payload && typeof payload === "object") {
    if ("detail" in payload) {
      return String(payload.detail);
    }

    if ("error" in payload) {
      return String(payload.error);
    }
  }

  return `Request failed with status ${response.status}`;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let lastError: Error | null = null;

  for (const apiBase of getApiBaseCandidates()) {
    try {
      const response = await fetch(`${apiBase}${path}`, {
        headers: {
          "Content-Type": "application/json",
          ...(init?.headers ?? {}),
        },
        ...init,
      });

      if (!response.ok) {
        throw new Error(await parseError(response));
      }

      return response.json() as Promise<T>;
    } catch (error) {
      lastError = error instanceof Error ? error : new Error("Request failed.");

      // Only fall through to the next candidate for network-level failures.
      if (!/Failed to fetch|NetworkError|Load failed/i.test(lastError.message)) {
        throw lastError;
      }
    }
  }

  throw lastError ?? new Error("Request failed.");
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

export function runBaselines(force = false) {
  if (force) {
    baselineResultsCache = null;
    baselineResultsPromise = null;
  }

  if (baselineResultsCache) {
    return Promise.resolve(baselineResultsCache);
  }

  if (baselineResultsPromise) {
    return baselineResultsPromise;
  }

  baselineResultsPromise = request<BaselineResults>("/baseline", {
    method: "POST",
  })
    .then((response) => {
      baselineResultsCache = response;
      return response;
    })
    .finally(() => {
      baselineResultsPromise = null;
    });

  return baselineResultsPromise;
}

export function gradeTrajectory(trajectory: TrajectoryStep[]) {
  return request<{ score: number }>("/grader", {
    method: "POST",
    body: JSON.stringify(trajectory),
  });
}

// New agent management functions
export function getAgents() {
  return request<{ available: string[]; current: string }>("/agents");
}

export function switchAgent(agentName: string) {
  return request<{ message: string; agent: string }>(`/agents/${agentName}`, {
    method: "POST",
  });
}

export function getSimpleMetrics() {
  return request<any>("/metrics");
}

export function resetSimpleMetrics() {
  return request<{ message: string }>("/metrics/reset", {
    method: "POST",
  });
}

export function getAutoStatus() {
  return request<AutoRunnerStatus>("/auto/status");
}

export function startAutoRunner(payload?: { interval?: number; task_id?: string | null }) {
  return request<AutoRunnerStatus>("/auto/start", {
    method: "POST",
    body: JSON.stringify(payload ?? {}),
  });
}

export function stopAutoRunner() {
  return request<AutoRunnerStatus>("/auto/stop", {
    method: "POST",
  });
}

export function getSystemLogs() {
  return request<SystemLogEntry[]>("/logs");
}
