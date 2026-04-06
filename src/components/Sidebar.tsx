import type { PageId } from "../App";
import { cn } from "../lib/cn";

type SidebarProps = {
  activePage: PageId;
  items: Array<{ id: PageId; label: string }>;
  onNavigate: (page: PageId) => void;
};

export function Sidebar({ activePage, items, onNavigate }: SidebarProps) {
  return (
    <>
      <aside className="fixed inset-x-0 top-0 z-20 border-b border-gray-200 bg-white/95 backdrop-blur md:inset-y-0 md:left-0 md:w-[240px] md:border-b-0 md:border-r">
        <div className="flex h-full flex-col">
          <div className="border-b border-gray-200 p-6">
            <p className="text-lg font-semibold text-gray-900">ASCDC</p>
            <p className="mt-1 text-sm text-gray-500">Decision intelligence dashboard</p>
          </div>

          <nav className="flex gap-2 overflow-x-auto p-4 md:flex-1 md:flex-col md:overflow-visible md:p-6">
            {items.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => onNavigate(item.id)}
                className={cn(
                  "rounded-2xl border p-4 text-left text-sm font-medium shadow-sm transition-all duration-200",
                  activePage === item.id
                    ? "border-blue-500 bg-blue-50 text-blue-600"
                    : "border-white/60 bg-white text-gray-600 hover:border-gray-200 hover:text-gray-900",
                )}
              >
                {item.label}
              </button>
            ))}
          </nav>
        </div>
      </aside>
    </>
  );
}
