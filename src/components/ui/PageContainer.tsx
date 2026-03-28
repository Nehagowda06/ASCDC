import type { PropsWithChildren } from "react";

type PageContainerProps = PropsWithChildren<{
  title: string;
  subtitle: string;
}>;

export function PageContainer({ title, subtitle, children }: PageContainerProps) {
  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <h1 className="text-xl font-medium text-gray-900">{title}</h1>
        <p className="max-w-3xl text-sm text-gray-500">{subtitle}</p>
      </div>
      {children}
    </div>
  );
}
