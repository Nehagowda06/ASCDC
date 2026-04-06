import { Card } from "../ui/Card";
import { formatNumber, formatPercent } from "../../lib/format";
import type { DecisionMetrics } from "../../lib/types";

type MetricsPanelProps = {
  metrics: DecisionMetrics;
};

export function MetricsPanel({ metrics }: MetricsPanelProps) {
  const safeTotalReward = Number.isFinite(metrics.totalReward) ? metrics.totalReward : 0;
  const safeNecessaryActionRatio = Number.isFinite(metrics.necessaryActionRatio)
    ? metrics.necessaryActionRatio
    : 0;
  const safePositiveImpactRate = Number.isFinite(metrics.positiveImpactRate)
    ? metrics.positiveImpactRate
    : 0;
  const safeAverageImpact = Number.isFinite(metrics.averageImpact) ? metrics.averageImpact : 0;

  const items = [
    {
      label: "Total Reward",
      value: formatNumber(safeTotalReward, 2),
      hint: "Aggregate reward from the current trajectory.",
      icon: "R",
      iconClassName: safeTotalReward >= 0 ? "bg-green-100 text-green-700" : "bg-red-100 text-red-700",
      valueClassName: safeTotalReward >= 0 ? "text-green-600" : "text-red-600",
    },
    {
      label: "Necessary Ratio",
      value: formatPercent(safeNecessaryActionRatio),
      hint: "How often interventions outperformed waiting.",
      icon: "N",
      iconClassName: "bg-blue-100 text-blue-700",
      valueClassName: "text-blue-600",
    },
    {
      label: "Positive Impact",
      value: formatPercent(safePositiveImpactRate),
      hint: "Share of non-noop actions with positive impact.",
      icon: "P",
      iconClassName: "bg-amber-100 text-amber-700",
      valueClassName: "text-amber-600",
    },
    {
      label: "Average Impact",
      value: formatNumber(safeAverageImpact, 2),
      hint: "Mean counterfactual impact across interventions.",
      icon: "A",
      iconClassName: safeAverageImpact >= 0 ? "bg-cyan-100 text-cyan-700" : "bg-red-100 text-red-700",
      valueClassName: safeAverageImpact >= 0 ? "text-cyan-600" : "text-red-600",
    },
  ];

  return (
    <div className="grid gap-6 md:grid-cols-2 xl:grid-cols-1 2xl:grid-cols-2">
      {items.map((item) => (
        <Card
          key={item.label}
          className="rounded-2xl border border-gray-200 bg-white p-6 text-gray-900 shadow-md transition-all duration-200 hover:scale-[1.01] hover:shadow-lg"
        >
          <div className="space-y-5">
            <div className="flex items-center gap-3">
              <div className={`inline-flex h-10 w-10 items-center justify-center rounded-2xl text-sm font-bold shadow-sm ${item.iconClassName}`}>
                {item.icon}
              </div>
              <div className="space-y-1">
                <p className="text-sm text-gray-500">
                  {item.label}
                </p>
                <p className={`text-2xl font-semibold ${item.valueClassName}`}>{item.value}</p>
              </div>
            </div>
            <p className="text-sm leading-6 text-gray-600">{item.hint}</p>
          </div>
        </Card>
      ))}
    </div>
  );
}
