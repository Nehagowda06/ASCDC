import type { ReactNode } from "react";

type Column<T> = {
  key: string;
  header: string;
  render: (row: T) => ReactNode;
};

type TableProps<T> = {
  columns: Array<Column<T>>;
  rows: T[];
  getRowKey: (row: T, index: number) => string;
  getRowClassName?: (row: T, index: number) => string | undefined;
  emptyMessage?: string;
};

export function Table<T>({
  columns,
  rows,
  getRowKey,
  getRowClassName,
  emptyMessage = "No records available.",
}: TableProps<T>) {
  return (
    <div className="overflow-hidden rounded-xl border border-[#242934] bg-[#14181f]">
      <table className="min-w-full border-collapse">
        <thead className="bg-[#171c24]">
          <tr>
            {columns.map((column) => (
              <th
                key={column.key}
                className="px-5 py-3.5 text-left text-[10px] font-medium uppercase tracking-[0.06em] text-gray-500"
              >
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td
                colSpan={columns.length}
                className="px-5 py-4 text-left text-[13px] text-gray-500"
              >
                {emptyMessage}
              </td>
            </tr>
          ) : (
            rows.map((row, index) => (
              <tr
                key={getRowKey(row, index)}
                className={`border-t border-[#20252e] ${getRowClassName?.(row, index) ?? ""}`}
              >
                {columns.map((column) => (
                  <td key={column.key} className="px-5 py-4 align-top text-[13px] text-gray-100">
                    {column.render(row)}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
