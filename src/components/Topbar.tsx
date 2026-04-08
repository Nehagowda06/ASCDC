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
    <div className="flex flex-col gap-3 rounded-[24px] border border-[#242934] bg-[#14181f] px-5 py-4 shadow-[0_1px_2px_rgba(0,0,0,0.2)] md:flex-row md:items-center md:justify-between">
      <div className="min-w-0">
        <p className="text-[10px] font-medium uppercase tracking-[0.08em] text-gray-400">
          Decision Intelligence
        </p>
        <h1 className="mt-1 text-[18px] font-semibold tracking-[-0.015em] text-white">ASCDC</h1>
        <p className="mt-1 text-[13px] text-gray-400">
          Adaptive System Control &amp; Decision Console
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <div className={`inline-flex items-center gap-2 rounded-full border px-3.5 py-2 text-[11px] font-medium ${statusPillClassName}`}>
          <span className={`h-2.5 w-2.5 rounded-full ${statusDotClassName}`} />
          {statusLabel}
        </div>
        <div className="rounded-full border border-[#2a3039] bg-[#171c24] px-3.5 py-2 text-[11px] text-gray-300">
          Current timestep <span className="font-semibold text-white">{timestep}</span>
        </div>
      </div>
    </div>
  );
}
