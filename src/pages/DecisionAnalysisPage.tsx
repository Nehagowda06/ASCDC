import { ActionComparison } from "../components/decision/ActionComparison";
import { DecisionPanel } from "../components/decision/DecisionPanel";
import { Card } from "../components/ui/Card";
import { PageContainer } from "../components/ui/PageContainer";
import { Section } from "../components/ui/Section";
import type { RecommendationResponse } from "../lib/types";

type DecisionAnalysisPageProps = {
  recommendation: RecommendationResponse | null;
  loading: boolean;
  onRefreshRecommendation: () => void;
};

export function DecisionAnalysisPage({
  recommendation,
  loading,
  onRefreshRecommendation,
}: DecisionAnalysisPageProps) {
  return (
    <PageContainer
      title="Analysis"
      subtitle="Inspect counterfactual rankings and understand how the operator distinguishes intervention from restraint."
    >
      <div className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
        <Section title="Decision summary" description="Recommended action with structured reasoning.">
          <DecisionPanel
            recommendation={recommendation}
            loading={loading}
            onRefresh={onRefreshRecommendation}
          />
        </Section>

        <Section title="Counterfactual comparison" description="Compare every candidate action against the noop baseline.">
          <ActionComparison rows={recommendation?.reasoning.alternative_actions ?? []} />
        </Section>
      </div>

      <Section title="Interpretation" description="What the recommendation means for the current operating posture.">
        <Card className="shadow-sm">
          <div className="space-y-3">
            <p className="text-sm text-gray-500">
              The operator evaluates restart, scale, throttle, and noop actions over a short horizon and compares them to waiting. Positive impact means the action improves projected reward relative to doing nothing.
            </p>
            <p className="text-sm text-gray-500">
              Necessary actions are the subset of interventions that outperform noop. When the best available intervention still underperforms waiting, the operator recommends noop.
            </p>
          </div>
        </Card>
      </Section>
    </PageContainer>
  );
}
