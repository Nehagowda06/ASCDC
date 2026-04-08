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
      iconClassName:
        safeTotalReward >= 0
          ? "border border-emerald-900/40 bg-emerald-500/10 text-emerald-300"
          : "border border-red-900/40 bg-red-500/10 text-red-300",
      valueClassName: safeTotalReward >= 0 ? "text-emerald-300" : "text-red-300",
    },
    {
      label: "Necessary Ratio",
      value: formatPercent(safeNecessaryActionRatio),
      hint: "How often interventions outperformed waiting.",
      icon: "N",
      iconClassName: "border border-[#C38EB4]/40 bg-[#C38EB4]/10 text-[#C38EB4]",
      valueClassName: "text-[#C38EB4]",
    },
    {
      label: "Positive Impact",
      value: formatPercent(safePositiveImpactRate),
      hint: "Share of non-noop actions with positive impact.",
      icon: "P",
      iconClassName: "border border-[#C38EB4]/40 bg-[#C38EB4]/10 text-[#C38EB4]",
      valueClassName: "text-[#C38EB4]",
    },
    {
      label: "Average Impact",
      value: formatNumber(safeAverageImpact, 2),
      hint: "Mean counterfactual impact across interventions.",
      icon: "A",
      iconClassName:
        safeAverageImpact >= 0
          ? "border border-cyan-900/40 bg-cyan-500/10 text-cyan-300"
          : "border border-red-900/40 bg-red-500/10 text-red-300",
      valueClassName: safeAverageImpact >= 0 ? "text-cyan-300" : "text-red-300",
    },
  ];

  return (
    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-1 2xl:grid-cols-2">
      {items.map((item) => (
        <Card
          key={item.label}
          className="bg-[#14181f] p-3.5 text-gray-100 shadow-sm"
        >
          <div className="space-y-2.5">
            <div className="flex items-center gap-3">
              <div className={`inline-flex h-8 w-8 items-center justify-center rounded-lg text-[13px] font-medium shadow-sm ${item.iconClassName}`}>
                {item.icon}
              </div>
              <div className="space-y-1">
                <p className="text-[12px] text-gray-400">
                  {item.label}
                </p>
                <p className={`text-[18px] font-semibold tracking-[-0.02em] ${item.valueClassName}`}>{item.value}</p>
              </div>
            </div>
            <p className="text-[13px] leading-5 text-gray-400">{item.hint}</p>
          </div>
        </Card>
      ))}
    </div>
  );
}
