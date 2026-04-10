import type { HTMLAttributes } from "react";

import { cn } from "../../lib/cn";

type CardProps = HTMLAttributes<HTMLDivElement>;

export function Card({ className, ...props }: CardProps) {
  return (
    <div
      className={cn(
        "rounded-2xl border border-[#242934] bg-[#14181f] p-3 shadow-[0_1px_2px_rgba(0,0,0,0.2)] transition-colors duration-150 hover:border-[#313845]",
        className,
      )}
      {...props}
    />
  );
}
