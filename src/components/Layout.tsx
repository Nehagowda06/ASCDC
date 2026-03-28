import type { PropsWithChildren } from "react";

import type { PageId } from "../App";
import { Sidebar } from "./Sidebar";

type LayoutProps = PropsWithChildren<{
  activePage: PageId;
  items: Array<{ id: PageId; label: string }>;
  onNavigate: (page: PageId) => void;
}>;

export function Layout({ activePage, items, onNavigate, children }: LayoutProps) {
  return (
    <div className="min-h-screen bg-gray-50 text-gray-900">
      <Sidebar activePage={activePage} items={items} onNavigate={onNavigate} />
      <main className="md:pl-[240px]">
        <div className="mx-auto max-w-content p-6 pt-24 md:p-6">{children}</div>
      </main>
    </div>
  );
}
