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
          <p className="text-xs font-medium uppercase tracking-[0.2em] text-gray-400">
            Action Comparison
          </p>
          <p className="text-lg font-semibold text-gray-900">
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
                  <span className="font-medium text-gray-900">
                    {row.label || formatActionLabel(row.action)}
                  </span>
                  {row.impact === bestImpact ? (
                    <span className="rounded-full bg-emerald-100 px-2 py-1 text-xs font-medium text-emerald-700">
                      Best
                    </span>
                  ) : null}
                  {row.impact === worstImpact ? (
                    <span className="rounded-full bg-red-100 px-2 py-1 text-xs font-medium text-red-700">
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
                <span className={row.impact > 0 ? "text-emerald-600" : row.impact < 0 ? "text-red-500" : "text-gray-500"}>
                  {row.impact > 0 ? "+" : ""}
                  {formatNumber(row.impact, 2)}
                </span>
              ),
            },
            {
              key: "necessary",
              header: "Necessary",
              render: (row) => (
                <span className={row.necessary ? "text-emerald-600" : "text-gray-500"}>
                  {row.action.type === "noop" ? "-" : row.necessary ? "true" : "false"}
                </span>
              ),
            },
          ]}
          rows={sortedRows}
          getRowKey={(row, index) => `${row.label}-${index}`}
          getRowClassName={(row) =>
            row.impact === bestImpact
              ? "bg-emerald-50"
              : row.impact === worstImpact
                ? "bg-red-50"
                : ""
          }
          emptyMessage="No action comparison available."
        />
      </div>
    </Card>
  );
}
