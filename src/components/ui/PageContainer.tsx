import type { PropsWithChildren } from "react";

type PageContainerProps = PropsWithChildren<{
  title: string;
  subtitle: string;
}>;

export function PageContainer({ title, subtitle, children }: PageContainerProps) {
  return (
    <div className="space-y-4">
      <div className="space-y-1.5">
        <h1>{title}</h1>
        <p className="max-w-3xl text-[13px] leading-6 text-gray-400">{subtitle}</p>
      </div>
      {children}
    </div>
  );
}
