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
  scale: "text-blue-600",
  throttle: "text-amber-600",
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
      <Card className="bg-white rounded-2xl shadow-md p-6 text-gray-900 border border-gray-200 transition-all duration-200 hover:shadow-lg hover:scale-[1.01]">
        <div className="space-y-3">
          <p className="text-xs font-medium uppercase tracking-[0.16em] text-gray-500">
            Decision Panel
          </p>
          <p className="text-lg font-semibold text-gray-900">No recommendation available</p>
          <p className="text-sm leading-6 text-gray-600">
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
    actionTextClassName[actionType as keyof typeof actionTextClassName] ?? "text-gray-900";
  const confidenceBarClassName =
    confidence >= 70
      ? "bg-green-500"
      : confidence >= 40
        ? "bg-amber-500"
        : "bg-red-500";

  return (
    <Card className="bg-white rounded-2xl shadow-md p-6 text-gray-900 border border-gray-200 transition-all duration-200 hover:shadow-lg hover:scale-[1.01]">
      <div className="space-y-6">
        <div className="space-y-4">
          <div className="flex flex-wrap items-center gap-3">
            <span className="inline-flex items-center rounded-full border border-gray-200 bg-gray-100 px-3 py-1 text-xs font-semibold uppercase tracking-[0.14em] text-gray-700">
              Recommended Action
            </span>
            <span className="text-xs uppercase tracking-[0.16em] text-gray-500">
              Counterfactual Decision
            </span>
          </div>

          {isNoop ? (
            <div className="rounded-2xl border border-amber-300 bg-amber-100 p-6 text-amber-900">
              <div className="space-y-2">
                <p className="text-3xl font-bold">No intervention recommended</p>
                <p className="text-sm leading-6 text-amber-800">
                  System stabilizes without action
                </p>
              </div>
            </div>
          ) : (
            <div className="rounded-2xl border border-gray-200 bg-gray-50 p-6">
              <div className="space-y-2">
                <p className="text-sm text-gray-500">Primary recommendation</p>
                <p className={`text-3xl font-bold ${actionClassName}`}>{actionLabel}</p>
              </div>
            </div>
          )}

          <p className="max-w-3xl text-sm leading-6 text-gray-600">
            {recommendation.reasoning.explanation ?? "Counterfactual simulation favors this action."}
          </p>
        </div>

        <div className="grid gap-6 md:grid-cols-3">
          <div className="rounded-2xl border border-gray-200 bg-gray-50 p-6 transition-all duration-200 hover:shadow-lg hover:scale-[1.01]">
            <div className="space-y-3">
              <div className="space-y-1">
                <p className="text-sm text-gray-500">Confidence</p>
                <p className="text-2xl font-semibold text-gray-900">{confidence}%</p>
              </div>
              <div className="h-2 rounded-full bg-gray-200">
                <div
                  className={`h-2 rounded-full transition-all duration-200 ${confidenceBarClassName}`}
                  style={{ width: `${Math.max(confidence, confidence > 0 ? 6 : 0)}%` }}
                />
              </div>
            </div>
          </div>

          <div className="rounded-2xl border border-gray-200 bg-gray-50 p-6 transition-all duration-200 hover:shadow-lg hover:scale-[1.01]">
            <p className="text-sm text-gray-500">Counterfactual Impact</p>
            <p className="mt-2 text-2xl font-semibold text-gray-900">
              {formatNumber(recommendation.reasoning.impact, 2)}
            </p>
          </div>

          <div className="rounded-2xl border border-gray-200 bg-gray-50 p-6 transition-all duration-200 hover:shadow-lg hover:scale-[1.01]">
            <p className="text-sm text-gray-500">Was action necessary?</p>
            <p className="mt-2 text-2xl font-semibold text-gray-900">
              {recommendation.reasoning.was_necessary ? "Yes" : "No"}
            </p>
          </div>
        </div>

        <div className="flex flex-wrap gap-4">
          {onApply ? (
            <Button
              disabled={loading}
              variant="primary"
              className="h-11 rounded-lg bg-blue-600 px-5 py-2 text-white shadow-md transition hover:scale-105 hover:bg-blue-700"
              onClick={onApply}
            >
              Use Recommendation
            </Button>
          ) : null}
          {onRefresh ? (
            <Button
              disabled={loading}
              variant="secondary"
              className="h-11 rounded-lg px-5 py-2 shadow-sm transition hover:scale-105"
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
