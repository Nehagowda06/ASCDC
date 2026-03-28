export type QueueKey = "A" | "B" | "C";
export type QueueMap = Record<string, number>;

export type PendingAction = {
  type: string;
  target: string | null;
  applies_at: number;
};

export type FailureFlags = {
  budget_exhausted?: boolean;
  queue_overflow?: boolean;
  latency_spike?: boolean;
  error_spike?: boolean;
  collapsed?: boolean;
};

export type Observation = {
  queues: QueueMap;
  capacities?: QueueMap;
  latencies?: QueueMap;
  latency?: number;
  retry_rate?: number;
  error_rate?: number;
  remaining_budget?: number;
  budget?: number;
  system_pressure?: number;
  pending_actions?: PendingAction[];
  timestep?: number;
};

export type EnvironmentState = Observation & {
  true_load?: QueueMap;
  delayed_effect_queue?: Record<string, Array<Record<string, unknown>>>;
  failure_flags?: FailureFlags;
  history?: TrajectoryStep[];
  seed?: number;
};

export type AgentAction = {
  type: string;
  target: string | null;
};

export type StepInfo = {
  latency: number;
  system_pressure: number;
  remaining_budget: number;
  queue_growth?: number;
  scheduled_timestep?: number;
  pressure_delta?: number;
  stability_score?: number;
  failure_flags: FailureFlags;
};

export type StepResponse = {
  observation: Observation;
  reward: number;
  done: boolean;
  info: StepInfo & Record<string, unknown>;
};

export type TaskItem = {
  name: string;
  description: string;
};

export type TaskMap = Record<string, TaskItem>;
export type BaselineResults = Record<string, Record<string, number>>;

export type TrajectoryStep = {
  timestep: number;
  observation: Observation;
  action: AgentAction;
  reward: number;
  next_observation: Observation;
  done: boolean;
  info: StepInfo & Record<string, unknown>;
};

export const EMPTY_OBSERVATION: Observation = {
  queues: { A: 0, B: 0, C: 0 },
  capacities: { A: 0, B: 0, C: 0 },
  latencies: { A: 0, B: 0, C: 0 },
  latency: 0,
  retry_rate: 0,
  error_rate: 0,
  remaining_budget: 0,
  budget: 0,
  system_pressure: 0,
  pending_actions: [],
  timestep: 0,
};

export const EMPTY_STATE: EnvironmentState = {
  ...EMPTY_OBSERVATION,
  failure_flags: {
    collapsed: false,
  },
  true_load: { A: 0, B: 0, C: 0 },
  history: [],
  seed: 42,
};
