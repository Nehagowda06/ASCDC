import { useEffect, useMemo, useState } from "react";

import { PageContainer } from "../components/ui/PageContainer";
import { Section } from "../components/ui/Section";
import { runBaselines } from "../lib/api";
import { formatNumber } from "../lib/format";
import type { BaselineResults } from "../lib/types";

type TaskComparison = {
  taskId: string;
  rankedAgents: Array<{
    agent: string;
    score: number;
  }>;
};

export function AgentComparisonPage({ onBackToTable }: { onBackToTable: () => void }) {
  const [results, setResults] = useState<BaselineResults>({});
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

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
  }, []);

  const comparisons = useMemo<TaskComparison[]>(() => {
    const taskIds = Object.keys(Object.values(results)[0] ?? {});

    return taskIds.map((taskId) => ({
      taskId,
      rankedAgents: Object.entries(results)
        .map(([agent, scores]) => ({
          agent,
          score: scores[taskId] ?? 0,
        }))
        .sort((left, right) => right.score - left.score),
    }));
  }, [results]);

  return (
    <PageContainer
      title="Agent Comparison"
      subtitle="Compare how each available agent performs on the same deterministic task set."
    >
      {loading ? (
        <div className="flex items-center justify-center py-8">
          <div className="h-8 w-8 animate-spin rounded-full border-b-2 border-[#C38EB4]"></div>
          <span className="ml-2 text-gray-400">Loading comparison results...</span>
        </div>
      ) : null}

      {error && !loading ? (
        <div className="rounded-xl border border-red-900/40 bg-red-500/10 p-4 text-sm text-red-300">{error}</div>
      ) : null}

      {!loading && !error ? (
        <Section
          title="Task-by-task comparison"
          description="Each task shows the actual switchable agents ranked from strongest to weakest score."
          actions={
            <button
              type="button"
              onClick={onBackToTable}
              className="inline-flex items-center rounded-full border border-[#2b313b] bg-[#171b21] px-3 py-1.5 text-[12px] font-medium text-gray-100 shadow-sm transition-colors hover:border-[#39404c] hover:bg-[#1b2028]"
            >
              Table view
            </button>
          }
        >
          <div className="grid gap-4 xl:grid-cols-3">
            {comparisons.map((comparison) => (
              <div key={comparison.taskId} className="rounded-xl border border-[#242934] bg-[#14181f] p-3.5 shadow-sm">
                <div className="space-y-1">
                  <p className="text-[10px] font-medium uppercase tracking-[0.08em] text-gray-500">Task</p>
                  <h3 className="text-[13px] font-semibold tracking-[-0.01em] text-white">{comparison.taskId}</h3>
                </div>

                <div className="mt-3 space-y-2.5">
                  {comparison.rankedAgents.map((entry, index) => {
                    const isLeader = index === 0;

                    return (
                      <div
                        key={`${comparison.taskId}-${entry.agent}`}
                        className={`rounded-xl border px-4 py-2.5 ${
                          isLeader
                            ? "border-emerald-900/40 bg-emerald-500/10"
                            : "border-[#2a3039] bg-[#171c24]"
                        }`}
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="space-y-1">
                            <p className="text-[12px] font-semibold text-white">{entry.agent}</p>
                          </div>
                          <div className="text-right">
                            <p className={`text-[12px] font-semibold tabular-nums ${isLeader ? "text-emerald-300" : "text-white"}`}>
                              {formatNumber(entry.score, 4)}
                            </p>
                            <p className="text-[10px] uppercase tracking-[0.08em] text-gray-500">
                              {isLeader ? "Best score" : `Rank ${index + 1}`}
                            </p>
                          </div>
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        </Section>
      ) : null}
    </PageContainer>
  );
}
