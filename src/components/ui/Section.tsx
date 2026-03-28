import type { PropsWithChildren } from "react";

type SectionProps = PropsWithChildren<{
  title?: string;
  description?: string;
}>;

export function Section({ title, description, children }: SectionProps) {
  return (
    <section className="space-y-4">
      {(title || description) && (
        <div className="space-y-1">
          {title ? <h2 className="text-lg font-medium text-gray-900">{title}</h2> : null}
          {description ? <p className="text-sm text-gray-500">{description}</p> : null}
        </div>
      )}
      {children}
    </section>
  );
}
