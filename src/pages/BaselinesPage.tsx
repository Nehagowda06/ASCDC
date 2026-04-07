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
  const [loading, setLoading] = useState<boolean>(true);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);

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
      subtitle="A minimal comparison table for the built-in agent strategies across every task."
    >
      {loading && (
        <div className="flex items-center justify-center py-8">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
          <span className="ml-2 text-gray-600">Running baseline evaluations...</span>
        </div>
      )}
      
      {error && !loading && (
        <div className="bg-red-50 border border-red-200 rounded-md p-4 mb-6">
          <div className="flex">
            <div className="flex-shrink-0">
              <svg className="h-5 w-5 text-red-400" viewBox="0 0 20 20" fill="currentColor">
                <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
              </svg>
            </div>
            <div className="ml-3">
              <h3 className="text-sm font-medium text-red-800">Evaluation Error</h3>
              <div className="mt-2 text-sm text-red-700">
                <p>{error}</p>
              </div>
              <div className="mt-4">
                <button
                  onClick={() => setReloadKey((current) => current + 1)}
                  className="inline-flex items-center px-3 py-2 border border-transparent text-sm leading-4 font-medium rounded-md text-red-700 bg-red-100 hover:bg-red-200 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-red-500"
                >
                  Retry
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {!loading && !error && (
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
                render: (row: BaselineRow) => {
                  const score = row.scores[taskId];
                  const scoreClass = score >= 0.7 ? "text-green-600" : score >= 0.4 ? "text-yellow-600" : "text-red-600";
                  return (
                    <span className={`font-medium ${scoreClass}`}>
                      {formatNumber(score, 4)}
                    </span>
                  );
                },
              })),
            ]}
            emptyMessage="Baseline evaluation results are not available."
            getRowKey={(row) => row.agent}
            rows={rows}
          />
        </Section>
      )}
    </PageContainer>
  );
}
