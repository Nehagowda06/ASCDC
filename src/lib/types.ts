export type EnvironmentState = {
  timestep?: number;
  queues: Record<string, number>;
  capacities?: Record<string, number>;
  latencies?: Record<string, number>;
  latency?: number;
  retry_rate?: number;
  error_rate?: number;
  remaining_budget?: number;
  budget?: number;
  system_pressure?: number;
  pending_actions?: PendingAction[];
  instability_score?: number;
  smoothed_drift?: number;
  failure_flags?: FailureFlags;
  done?: boolean;
};

export type FailureFlags = {
  collapsed?: boolean;
};

export type PendingAction = {
  type: string;
  target?: string;
  applies_at: number;
};

export type AgentAction = {
  type: string;
  action_type: string;
  target: string | null;
  amount?: number;
};

export type StepResponse = {
  observation: EnvironmentState;
  reward: number;
  done: boolean;
  info: StepInfo;
};

export type StepInfo = {
  latency?: number;
  stability?: number;
  pressure_delta?: number;
  necessity?: boolean;
  timing_window?: boolean;
  counterfactual_impact?: number;
  was_action_necessary?: boolean;
  had_meaningful_impact?: boolean;
  failure_flags?: FailureFlags;
  system_pressure?: number;
  remaining_budget?: number;
  instability_score?: number;
  smoothed_drift?: number;
  [key: string]: unknown;
};

export type Observation = EnvironmentState;

export type TrajectoryStep = {
  timestep: number;
  observation: EnvironmentState;
  action: AgentAction;
  reward: number;
  next_observation: EnvironmentState;
  done: boolean;
  info: StepInfo;
};

export type RecommendationResponse = {
  action: AgentAction;
  impact: number;
  was_necessary: boolean;
  confidence: number;
  explanation: string;
  evaluated_actions: EvaluatedAction[];
  reasoning: RecommendationReasoning;
};

export type EvaluatedAction = {
  action: AgentAction;
  label: string;
  impact: number;
  necessary: boolean;
};

export type RecommendationReasoning = {
  best_action: string;
  confidence: number;
  impact: number;
  was_necessary: boolean;
  alternative_actions: EvaluatedAction[];
  explanation: string;
  agent_name?: string;
  agent_action?: string;
  agent_action_impact?: number;
  agent_action_rank?: number;
  agent_action_matches_best?: boolean;
};

export type DecisionMetrics = {
  totalReward: number;
  necessaryActionRatio: number;
  averageImpact: number;
  positiveImpactRate: number;
};

export type AutoRunnerStatus = {
  running: boolean;
  state?: EnvironmentState;
  last_action?: AgentAction;
};

export type SystemLogEntry = {
  timestep: number;
  action: string;
  pressure: number;
  instability: number;
  counterfactual_impact: number;
  decision_rationale: string;
};

export type TaskMap = Record<string, TaskDefinition>;

export type TaskDefinition = {
  name: string;
  description?: string;
  config: TaskConfig;
};

export type TaskConfig = {
  seed?: number;
  base_load?: Record<string, number>;
  capacities?: Record<string, number>;
  initial_queues?: Record<string, number>;
  initial_budget?: number;
  max_timesteps?: number;
};

export type BaselineResults = {
  [agentName: string]: {
    score: number;
    total_reward: number;
    steps: number;
    collapsed: boolean;
  };
};

export const EMPTY_STATE: EnvironmentState = {
  timestep: 0,
  queues: { A: 0, B: 0, C: 0 },
  capacities: { A: 10, B: 10, C: 10 },
  latencies: { A: 1, B: 1, C: 1 },
  latency: 1,
  retry_rate: 0,
  error_rate: 0,
  remaining_budget: 100,
  budget: 100,
  system_pressure: 0,
  pending_actions: [],
  instability_score: 0,
  smoothed_drift: 0,
  failure_flags: { collapsed: false },
  done: false,
};
