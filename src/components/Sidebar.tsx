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
      <aside className="fixed inset-x-0 top-0 z-20 border-b border-[#20252c] bg-[#111317]/95 backdrop-blur md:inset-y-0 md:left-0 md:w-[248px] md:border-b-0 md:border-r">
        <div className="flex h-full flex-col">
          <nav className="flex gap-2 overflow-x-auto p-3 md:flex-1 md:flex-col md:overflow-visible md:p-5">
            {items.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => onNavigate(item.id)}
                className={cn(
                  "rounded-xl border px-4 py-2.5 text-left text-[13px] font-medium transition-colors duration-150",
                  activePage === item.id
                    ? "border-[#2e3640] bg-[#1a1f26] text-white"
                    : "border-transparent bg-transparent text-gray-300 hover:border-[#232933] hover:bg-[#171b21] hover:text-white",
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
