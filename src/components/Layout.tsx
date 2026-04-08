import type { PropsWithChildren } from "react";

import type { PageId } from "../App";
import { Sidebar } from "./Sidebar";
import { Topbar } from "./Topbar";

type LayoutProps = PropsWithChildren<{
  activePage: PageId;
  items: Array<{ id: PageId; label: string }>;
  onNavigate: (page: PageId) => void;
  statusLabel: string;
  statusDotClassName: string;
  statusPillClassName: string;
  timestep: number;
}>;

export function Layout({
  activePage,
  items,
  onNavigate,
  statusLabel,
  statusDotClassName,
  statusPillClassName,
  timestep,
  children,
}: LayoutProps) {
  return (
    <div className="min-h-screen bg-[#0f1115] text-gray-100">
      <Sidebar activePage={activePage} items={items} onNavigate={onNavigate} />
      <main className="md:pl-[248px]">
        <div className="mx-auto max-w-content space-y-5 p-3 pt-20 md:p-5 md:pt-5">
          <Topbar
            statusLabel={statusLabel}
            statusDotClassName={statusDotClassName}
            statusPillClassName={statusPillClassName}
            timestep={timestep}
          />
          {children}
        </div>
      </main>
    </div>
  );
}
