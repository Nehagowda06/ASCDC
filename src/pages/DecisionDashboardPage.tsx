import { DecisionPanel } from "../components/decision/DecisionPanel";
import { MetricsPanel } from "../components/decision/MetricsPanel";
import { Timeline, type TimelinePoint } from "../components/decision/Timeline";
import type { DecisionMetrics, RecommendationResponse } from "../lib/types";

type DecisionDashboardPageProps = {
  recommendation: RecommendationResponse | null;
  metrics: DecisionMetrics;
  timeline: TimelinePoint[];
  loading: boolean;
  onApplyRecommendation: () => void;
  onRefreshRecommendation: () => void;
};

export function DecisionDashboardPage({
  recommendation,
  metrics,
  timeline,
  loading,
  onApplyRecommendation,
  onRefreshRecommendation,
}: DecisionDashboardPageProps) {
  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 px-6 py-6 text-gray-900">
      <div className="mx-auto max-w-7xl space-y-8">
        <div className="space-y-2">
          <div className="inline-flex items-center rounded-full border border-gray-200 bg-white px-3 py-1 text-xs font-medium uppercase tracking-[0.16em] text-gray-500 shadow-sm">
            Decision Intelligence Dashboard
          </div>
          <div className="space-y-2">
            <h1 className="text-3xl font-bold text-gray-900">Dashboard</h1>
            <p className="max-w-3xl text-sm leading-6 text-gray-600">
              A live decision workspace for evaluating whether the system should act, wait, or compare alternatives.
            </p>
          </div>
        </div>

        <div className="grid items-start gap-6 xl:grid-cols-[1.2fr_0.8fr]">
          <div className="space-y-4">
            <div className="space-y-1">
              <p className="text-lg font-semibold text-gray-900">Recommendation</p>
              <p className="text-sm text-gray-500">
                Autonomous operator guidance based on counterfactual simulation.
              </p>
            </div>
            <DecisionPanel
              recommendation={recommendation}
              loading={loading}
              onApply={onApplyRecommendation}
              onRefresh={onRefreshRecommendation}
            />
          </div>

          <div className="space-y-4">
            <div className="space-y-1">
              <p className="text-lg font-semibold text-gray-900">Decision Metrics</p>
              <p className="text-sm text-gray-500">
                Outcome quality across the trajectory so far.
              </p>
            </div>
            <MetricsPanel metrics={metrics} />
          </div>
        </div>

        <div className="space-y-4">
          <div className="space-y-1">
            <p className="text-lg font-semibold text-gray-900">Timeline</p>
            <p className="text-sm text-gray-500">
              Follow queue levels, interventions, and delayed effects across recent steps.
            </p>
          </div>
          <Timeline points={timeline} />
        </div>
      </div>
    </div>
  );
}
