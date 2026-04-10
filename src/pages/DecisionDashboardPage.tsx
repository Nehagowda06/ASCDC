import { DecisionPanel } from "../components/decision/DecisionPanel";
import { MetricsPanel } from "../components/decision/MetricsPanel";
import { Timeline, type TimelinePoint } from "../components/decision/Timeline";
import { PageContainer } from "../components/ui/PageContainer";
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
    <PageContainer
      title="Dashboard"
      subtitle="A live decision workspace for evaluating whether the system should act, wait, or compare alternatives."
    >
      <div className="space-y-4">
        <div className="grid items-start gap-4 xl:grid-cols-12">
          <div className="space-y-3 xl:col-span-7">
            <div className="space-y-1">
              <h3>Recommendation</h3>
              <p className="text-[13px] leading-5 text-gray-400">
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

          <div className="space-y-3 xl:col-span-5">
            <div className="space-y-1">
              <h3>Decision Metrics</h3>
              <p className="text-[13px] leading-5 text-gray-400">
                Outcome quality across the trajectory so far.
              </p>
            </div>
            <MetricsPanel metrics={metrics} />
          </div>
        </div>

        <div className="space-y-3">
          <div className="space-y-1">
            <h3>Timeline</h3>
            <p className="text-[13px] leading-5 text-gray-400">
              Follow queue levels, interventions, and delayed effects across recent steps.
            </p>
          </div>
          <Timeline points={timeline} />
        </div>
      </div>
    </PageContainer>
  );
}
