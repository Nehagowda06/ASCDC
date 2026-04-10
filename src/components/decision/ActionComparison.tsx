import { Card } from "../ui/Card";
import { Table } from "../ui/Table";
import { formatActionLabel } from "../../lib/decision";
import { formatNumber } from "../../lib/format";
import type { RecommendationAlternative } from "../../lib/types";

type ActionComparisonProps = {
  rows: RecommendationAlternative[];
};

export function ActionComparison({ rows }: ActionComparisonProps) {
  const sortedRows = [...rows].sort((left, right) => right.impact - left.impact);
  const bestImpact = sortedRows[0]?.impact;
  const worstImpact = sortedRows[sortedRows.length - 1]?.impact;

  return (
    <Card className="shadow-sm">
      <div className="space-y-4">
        <div className="space-y-1">
          <p className="text-[11px] font-medium uppercase tracking-[0.08em] text-gray-400">
            Action Comparison
          </p>
          <p className="text-lg font-medium text-white">
            Counterfactual ranking across available interventions
          </p>
        </div>

        <Table<RecommendationAlternative>
          columns={[
            {
              key: "action",
              header: "Action",
              render: (row) => (
                <div className="flex items-center gap-2">
                  <span className="text-[14px] font-medium text-white">
                    {row.label || formatActionLabel(row.action)}
                  </span>
                  {row.impact === bestImpact ? (
                    <span className="rounded-full border border-emerald-900/40 bg-emerald-500/10 px-2 py-1 text-[10px] font-medium uppercase tracking-[0.04em] text-emerald-300">
                      Best
                    </span>
                  ) : null}
                  {row.impact === worstImpact ? (
                    <span className="rounded-full border border-red-900/40 bg-red-500/10 px-2 py-1 text-[10px] font-medium uppercase tracking-[0.04em] text-red-300">
                      Worst
                    </span>
                  ) : null}
                </div>
              ),
            },
            {
              key: "impact",
              header: "Impact",
              render: (row) => (
                <span className={`text-[14px] font-medium ${row.impact > 0 ? "text-emerald-300" : row.impact < 0 ? "text-red-300" : "text-gray-400"}`}>
                  {row.impact > 0 ? "+" : ""}
                  {formatNumber(row.impact, 2)}
                </span>
              ),
            },
            {
              key: "necessary",
              header: "Necessary",
              render: (row) => (
                <span className={`text-[14px] font-medium ${row.necessary ? "text-emerald-300" : "text-gray-500"}`}>
                  {row.action.type === "noop" ? "-" : row.necessary ? "true" : "false"}
                </span>
              ),
            },
          ]}
          rows={sortedRows}
          getRowKey={(row, index) => `${row.label}-${index}`}
          getRowClassName={(row) =>
            row.impact === bestImpact
              ? "bg-emerald-500/10"
              : row.impact === worstImpact
                ? "bg-red-500/10"
                : ""
          }
          emptyMessage="No action comparison available."
        />
      </div>
    </Card>
  );
}
