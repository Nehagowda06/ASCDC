import { useEffect, useState } from "react";

import { PageContainer } from "../components/ui/PageContainer";
import { Section } from "../components/ui/Section";
import { Table } from "../components/ui/Table";
import { runBaselines } from "../lib/api";
import { formatNumber } from "../lib/format";
import type { BaselineResults } from "../lib/types";

type BaselineRow = {
  agent: string;
  scores: Record<string, number>;
};

export function BaselinesPage() {
  const [results, setResults] = useState<BaselineResults>({});
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    runBaselines()
      .then((response) => {
        if (!cancelled) {
          setResults(response);
          setError(null);
        }
      })
      .catch((nextError: Error) => {
        if (!cancelled) {
          setError(nextError.message);
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const taskIds = Object.keys(Object.values(results)[0] ?? {});
  const rows: BaselineRow[] = Object.entries(results).map(([agent, scores]) => ({
    agent,
    scores,
  }));

  return (
    <PageContainer
      title="Baselines"
      subtitle="A minimal comparison table for the built-in agent strategies across every task."
    >
      {error ? <p className="text-sm text-red-500">{error}</p> : null}

      <Section title="Agent scores" description="Each score is graded on the same deterministic trajectory rubric.">
        <Table<BaselineRow>
          columns={[
            {
              key: "agent",
              header: "Agent",
              render: (row) => <span className="font-medium text-gray-900">{row.agent}</span>,
            },
            ...taskIds.map((taskId) => ({
              key: taskId,
              header: taskId,
              render: (row: BaselineRow) => formatNumber(row.scores[taskId], 4),
            })),
          ]}
          emptyMessage="Baseline evaluation results are not available."
          getRowKey={(row) => row.agent}
          rows={rows}
        />
      </Section>
    </PageContainer>
  );
}
