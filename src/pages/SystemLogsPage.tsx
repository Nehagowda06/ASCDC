import { Card } from "../components/ui/Card";
import { PageContainer } from "../components/ui/PageContainer";
import { Section } from "../components/ui/Section";
import { formatActionLabel } from "../lib/decision";
import { formatNumber } from "../lib/format";
import type { SystemLogEntry } from "../lib/types";

type SystemLogsPageProps = {
  logs: SystemLogEntry[];
  loading?: boolean;
  error?: string | null;
};

function getRowClassName(log: SystemLogEntry) {
  if ((log.instability ?? 0) >= 1) {
    return "border-red-900/40 bg-red-500/10";
  }

  if ((log.counterfactual ?? 0) > 0) {
    return "border-emerald-900/40 bg-emerald-500/10";
  }

  return "border-[#242934] bg-[#171c24]";
}

function getBadge(log: SystemLogEntry) {
  if ((log.instability ?? 0) >= 1) {
    return (
      <span className="rounded-full border border-red-900/40 bg-red-500/10 px-2 py-1 text-xs font-medium text-red-300">
        High instability
      </span>
    );
  }

  if ((log.counterfactual ?? 0) > 0) {
    return (
      <span className="rounded-full border border-emerald-900/40 bg-emerald-500/10 px-2 py-1 text-xs font-medium text-emerald-300">
        Positive counterfactual
      </span>
    );
  }

  return null;
}

export function SystemLogsPage({ logs, loading = false, error }: SystemLogsPageProps) {
  const rows = [...logs].reverse();

  return (
    <PageContainer
      title="System Logs"
      subtitle="Lightweight live diagnostics showing how each environment step changed reward, pressure, and instability."
    >
      {error ? <p className="text-sm text-red-300">{error}</p> : null}

      <Section
        title="Live step log"
        description="The list refreshes every second while this page is open so you can inspect real-time decisions without switching tools."
      >
        <Card className="shadow-sm">
          <div className="space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="space-y-1">
                <p className="text-xs font-medium uppercase tracking-[0.2em] text-gray-400">Recent events</p>
                <p className="text-sm text-gray-400">{rows.length} buffered step logs</p>
              </div>
              {loading ? <p className="text-sm text-gray-400">Refreshing...</p> : null}
            </div>

            <div className="max-h-[620px] space-y-3 overflow-y-auto pr-1">
              {rows.length === 0 ? (
                <div className="rounded-xl border border-dashed border-[#2b313b] bg-[#171c24] p-4 text-sm text-gray-400">
                  No logs yet. Step the environment or start auto mode to populate the stream.
                </div>
              ) : (
                rows.map((log, index) => (
                  <div
                    key={`${log.timestep}-${index}`}
                    className={`rounded-xl border p-4 transition-all duration-200 ${getRowClassName(log)}`}
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div className="space-y-2">
                        <div className="flex flex-wrap items-center gap-3">
                          <p className="text-sm font-semibold text-white">Timestep {log.timestep}</p>
                          {getBadge(log)}
                        </div>
                        <p className="text-sm text-gray-300">{formatActionLabel(log.action)}</p>
                      </div>
                      <p className="text-xs uppercase tracking-[0.16em] text-gray-500">System log</p>
                    </div>

                    <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
                      <div className="rounded-xl bg-[#11161d] px-3 py-2">
                        <p className="text-xs text-gray-500">Reward</p>
                        <p className="text-sm font-medium text-white">{formatNumber(log.reward, 3)}</p>
                      </div>
                      <div className="rounded-xl bg-[#11161d] px-3 py-2">
                        <p className="text-xs text-gray-500">Pressure</p>
                        <p className="text-sm font-medium text-white">{formatNumber(log.pressure, 3)}</p>
                      </div>
                      <div className="rounded-xl bg-[#11161d] px-3 py-2">
                        <p className="text-xs text-gray-500">Instability</p>
                        <p className="text-sm font-medium text-white">{formatNumber(log.instability, 3)}</p>
                      </div>
                      <div className="rounded-xl bg-[#11161d] px-3 py-2 sm:col-span-2 xl:col-span-2">
                        <p className="text-xs text-gray-500">Counterfactual</p>
                        <p
                          className={`text-sm font-medium ${
                            (log.counterfactual ?? 0) > 0 ? "text-emerald-300" : "text-white"
                          }`}
                        >
                          {formatNumber(log.counterfactual, 3)}
                        </p>
                      </div>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </Card>
      </Section>
    </PageContainer>
  );
}
