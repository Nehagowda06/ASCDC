import type { PropsWithChildren, ReactNode } from "react";

type SectionProps = PropsWithChildren<{
  title?: string;
  description?: string;
  actions?: ReactNode;
}>;

export function Section({ title, description, actions, children }: SectionProps) {
  return (
    <section className="space-y-4">
      {(title || description) && (
        <div className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
          <div className="space-y-1">
            {title ? <h2>{title}</h2> : null}
            {description ? <p className="text-[13px] leading-6 text-gray-400">{description}</p> : null}
          </div>
          {actions ? <div className="shrink-0">{actions}</div> : null}
        </div>
      )}
      {children}
    </section>
  );
}
