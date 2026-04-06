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
    <div className="min-h-screen bg-gray-100 text-gray-900">
      <Sidebar activePage={activePage} items={items} onNavigate={onNavigate} />
      <main className="md:pl-[240px]">
        <div className="mx-auto max-w-content space-y-6 p-6 pt-24 md:p-6">
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
