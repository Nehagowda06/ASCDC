import type { PropsWithChildren } from "react";

import { Card } from "./Card";

type ChartWrapperProps = PropsWithChildren<{
  title: string;
  subtitle?: string;
}>;

export function ChartWrapper({ title, subtitle, children }: ChartWrapperProps) {
  return (
    <Card>
      <div className="space-y-4">
        <div className="space-y-1">
          <h3 className="text-lg font-medium text-gray-900">{title}</h3>
          {subtitle ? <p className="text-sm text-gray-500">{subtitle}</p> : null}
        </div>
        <div className="h-72">{children}</div>
      </div>
    </Card>
  );
}
