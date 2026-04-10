import { Button } from "../ui/Button";
import { Card } from "../ui/Card";
import { formatActionLabel } from "../../lib/decision";
import { formatNumber } from "../../lib/format";
import type { RecommendationResponse } from "../../lib/types";

type DecisionPanelProps = {
  recommendation: RecommendationResponse | null;
  loading?: boolean;
  onApply?: () => void;
  onRefresh?: () => void;
};

const actionTextClassName = {
  scale: "text-[#C38EB4]",
  throttle: "text-[#C38EB4]",
  restart: "text-red-600",
  noop: "text-yellow-600",
} as const;

export function DecisionPanel({
  recommendation,
  loading = false,
  onApply,
  onRefresh,
}: DecisionPanelProps) {
  if (!recommendation) {
    return (
      <Card className="bg-[#14181f] text-gray-100 shadow-sm">
        <div className="space-y-2.5">
          <p className="text-[11px] font-medium uppercase tracking-[0.1em] text-gray-500">
            Decision Panel
          </p>
          <p className="text-base font-semibold text-white">No recommendation available</p>
          <p className="text-sm leading-6 text-gray-400">
            Fetch a recommendation to compare action impact against the noop baseline.
          </p>
        </div>
      </Card>
    );
  }

  const actionType = (recommendation.action.type ?? recommendation.action.action_type ?? "noop").toLowerCase();
  const actionLabel = formatActionLabel(recommendation.action);
  const confidence = Math.round((recommendation.reasoning.confidence ?? 0) * 100);
  const isNoop = actionType === "noop";
  const actionClassName =
    actionTextClassName[actionType as keyof typeof actionTextClassName] ?? "text-white";
  const confidenceBarClassName =
    confidence >= 70
      ? "bg-green-500"
      : confidence >= 40
        ? "bg-[#C38EB4]"
        : "bg-red-500";
  const showAgentOverride =
    recommendation.reasoning.agent_action_matches_best === false &&
    recommendation.reasoning.agent_action &&
    recommendation.reasoning.agent_name;
  const noopSummary = recommendation.reasoning.explanation?.includes("stable enough")
    ? "Waiting is the strongest option right now"
    : "Intervening now scores worse than waiting";

  return (
    <Card className="bg-[#14181f] text-gray-100 shadow-sm">
      <div className="space-y-3">
        <div className="space-y-3">
          <div className="flex flex-wrap items-center gap-2.5">
            <span className="inline-flex items-center rounded-full border border-[#2a3039] bg-[#171c24] px-3 py-1 text-[11px] font-medium uppercase tracking-[0.08em] text-gray-400">
              Recommended Action
            </span>
            <span className="text-[11px] uppercase tracking-[0.08em] text-gray-500">
              Counterfactual Decision
            </span>
          </div>

          {isNoop ? (
            <div className="rounded-xl border border-[#C38EB4]/40 bg-[#C38EB4]/10 p-3.5 text-[#E2C7D8]">
              <div className="space-y-1.5">
                <p className="text-[18px] font-semibold tracking-[-0.02em]">No intervention recommended</p>
                <p className="text-sm leading-6 text-[#D6B4CA]">
                  {noopSummary}
                </p>
              </div>
            </div>
          ) : (
            <div className="rounded-xl border border-[#2a3039] bg-[#171c24] p-3.5">
              <div className="space-y-1.5">
                <p className="text-[11px] uppercase tracking-[0.08em] text-gray-500">Primary recommendation</p>
                <p className={`text-[18px] font-semibold tracking-[-0.02em] ${actionClassName}`}>{actionLabel}</p>
              </div>
            </div>
          )}

          <p className="max-w-3xl text-sm leading-7 text-gray-300">
            {recommendation.reasoning.explanation ?? "Counterfactual simulation favors this action."}
          </p>

          {showAgentOverride ? (
            <div className="rounded-xl border border-[#C38EB4]/40 bg-[#C38EB4]/10 p-3.5 text-sm text-[#E2C7D8]">
              <p className="font-medium">
                {recommendation.reasoning.agent_name} proposed {recommendation.reasoning.agent_action}.
              </p>
              <p className="mt-1 leading-6 text-[#D6B4CA]">
                It ranked {recommendation.reasoning.agent_action_rank ?? "?"} in the counterfactual comparison
                {typeof recommendation.reasoning.agent_action_impact === "number"
                  ? ` with impact ${formatNumber(recommendation.reasoning.agent_action_impact, 2)}.`
                  : "."}
              </p>
            </div>
          ) : null}
        </div>

        <div className="grid gap-3 md:grid-cols-3">
          <div className="rounded-xl border border-[#2a3039] bg-[#171c24] p-3.5 transition-all duration-200">
              <div className="space-y-2.5">
                <div className="space-y-1">
                  <p className="text-[12px] text-gray-500">Confidence</p>
                  <p className="text-[16px] font-semibold tracking-[-0.01em] text-white">{confidence}%</p>
                </div>
              <div className="h-2 rounded-full bg-[#232935]">
                <div
                  className={`h-2 rounded-full transition-all duration-200 ${confidenceBarClassName}`}
                  style={{ width: `${Math.max(confidence, confidence > 0 ? 6 : 0)}%` }}
                />
              </div>
            </div>
          </div>

          <div className="rounded-xl border border-[#2a3039] bg-[#171c24] p-3.5 transition-all duration-200">
            <p className="text-[12px] text-gray-500">Counterfactual Impact</p>
            <p className="mt-1.5 text-[16px] font-semibold tracking-[-0.01em] text-white">
              {formatNumber(recommendation.reasoning.impact, 2)}
            </p>
          </div>

          <div className="rounded-xl border border-[#2a3039] bg-[#171c24] p-3.5 transition-all duration-200">
            <p className="text-[12px] text-gray-500">Was action necessary?</p>
            <p className="mt-1.5 text-[16px] font-semibold tracking-[-0.01em] text-white">
              {recommendation.reasoning.was_necessary ? "Yes" : "No"}
            </p>
          </div>
        </div>

        <div className="flex flex-wrap gap-3">
          {onApply ? (
            <Button
              disabled={loading}
              variant="primary"
              className="h-9 rounded-lg px-4 text-white shadow-sm"
              onClick={onApply}
            >
              Use Recommendation
            </Button>
          ) : null}
          {onRefresh ? (
            <Button
              disabled={loading}
              variant="secondary"
              className="h-9 rounded-lg px-4 shadow-sm"
              onClick={onRefresh}
            >
              Refresh Analysis
            </Button>
          ) : null}
        </div>
      </div>
    </Card>
  );
}
