import { Card } from "./ui/Card";

type TopbarProps = {
  statusLabel: string;
  statusDotClassName: string;
  statusPillClassName: string;
  timestep: number;
};

export function Topbar({
  statusLabel,
  statusDotClassName,
  statusPillClassName,
  timestep,
}: TopbarProps) {
  return (
    <Card className="sticky top-6 z-10 flex flex-col gap-4 border-white/60 bg-white/90 p-4 shadow-sm backdrop-blur md:flex-row md:items-center md:justify-between">
      <div className="space-y-1">
        <p className="text-xs font-medium uppercase tracking-[0.2em] text-gray-400">
          Decision Intelligence
        </p>
        <p className="text-lg font-semibold text-gray-900">Temporal Control Console</p>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <div className={`inline-flex items-center gap-2 rounded-full border px-3 py-2 text-sm font-medium ${statusPillClassName}`}>
          <span className={`h-2.5 w-2.5 rounded-full ${statusDotClassName}`} />
          {statusLabel}
        </div>
        <div className="rounded-full border border-gray-200 bg-gray-50 px-3 py-2 text-sm text-gray-600">
          Current timestep <span className="font-semibold text-gray-900">{timestep}</span>
        </div>
      </div>
    </Card>
  );
}
