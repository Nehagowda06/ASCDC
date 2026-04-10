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

export function BaselinesPage({ onOpenComparison }: { onOpenComparison: () => void }) {
  const [results, setResults] = useState<BaselineResults>({});
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    runBaselines(reloadKey > 0)
      .then((response) => {
        if (!cancelled) {
          setResults(response);
          setError(null);
        }
      })
      .catch((nextError: Error) => {
        if (!cancelled) {
          setError(nextError.message);
          setResults({});
        }
      })
      .finally(() => {
        if (!cancelled) {
          setLoading(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  const taskIds = Object.keys(Object.values(results)[0] ?? {});
  const rows: BaselineRow[] = Object.entries(results).map(([agent, scores]) => ({
    agent,
    scores,
  }));

  return (
    <PageContainer
      title="Baselines"
      subtitle="A minimal comparison table for the actual switchable agents across every task."
    >
      {loading ? (
        <div className="flex items-center justify-center py-8">
          <div className="h-8 w-8 animate-spin rounded-full border-b-2 border-[#C38EB4]"></div>
          <span className="ml-2 text-gray-400">Running baseline evaluations...</span>
        </div>
      ) : null}

      {error && !loading ? (
        <div className="mb-6 rounded-xl border border-red-900/40 bg-red-500/10 p-4">
          <div className="flex">
            <div className="flex-shrink-0">
              <svg className="h-5 w-5 text-red-300" viewBox="0 0 20 20" fill="currentColor">
                <path
                  fillRule="evenodd"
                  d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z"
                  clipRule="evenodd"
                />
              </svg>
            </div>
            <div className="ml-3">
              <h3 className="text-sm font-medium text-red-200">Evaluation Error</h3>
              <div className="mt-2 text-sm text-red-300">
                <p>{error}</p>
              </div>
              <div className="mt-4">
                <button
                  type="button"
                  onClick={() => setReloadKey((current) => current + 1)}
                  className="inline-flex items-center rounded-lg border border-red-900/40 bg-red-500/10 px-3 py-2 text-sm font-medium leading-4 text-red-200 transition-colors hover:bg-red-500/20 focus:outline-none"
                >
                  Retry
                </button>
              </div>
            </div>
          </div>
        </div>
      ) : null}

      {!loading && !error ? (
        <Section
          title="Agent scores"
          description="Each score is graded on the same deterministic trajectory rubric using the same live agent set shown in the Agents page."
          actions={
            <button
              type="button"
              onClick={onOpenComparison}
              className="inline-flex items-center rounded-full border border-[#2b313b] bg-[#171b21] px-3 py-2 text-[12px] font-medium text-gray-100 shadow-sm transition-colors hover:border-[#39404c] hover:bg-[#1b2028]"
            >
              Comparison view
            </button>
          }
        >
          <Table<BaselineRow>
            columns={[
              {
                key: "agent",
                header: "Agent",
                render: (row) => <span className="text-[13px] font-medium text-white">{row.agent}</span>,
              },
              ...taskIds.map((taskId) => ({
                key: taskId,
                header: taskId,
                render: (row: BaselineRow) => {
                  const score = row.scores[taskId];
                  const scoreClass =
                    score >= 0.7 ? "text-emerald-300" : score >= 0.4 ? "text-[#C38EB4]" : "text-red-300";
                  return <span className={`text-[13px] font-medium tabular-nums ${scoreClass}`}>{formatNumber(score, 4)}</span>;
                },
              })),
            ]}
            emptyMessage="Baseline evaluation results are not available."
            getRowKey={(row) => row.agent}
            rows={rows}
          />
        </Section>
      ) : null}
    </PageContainer>
  );
}
