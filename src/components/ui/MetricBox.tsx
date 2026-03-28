import { useEffect, useRef, useState } from "react";

import { cn } from "../../lib/cn";
import { Card } from "./Card";

type MetricBoxProps = {
  label: string;
  value: string;
  hint?: string;
  tone?: "default" | "latency" | "budget" | "warning" | "danger";
  trend?: string;
  className?: string;
};

const toneClasses: Record<NonNullable<MetricBoxProps["tone"]>, string> = {
  default: "text-gray-900",
  latency: "text-blue-600",
  budget: "text-green-600",
  warning: "text-yellow-500",
  danger: "text-red-500",
};

export function MetricBox({
  label,
  value,
  hint,
  tone = "default",
  trend,
  className,
}: MetricBoxProps) {
  const [isChanged, setIsChanged] = useState(false);
  const previousValue = useRef(value);

  useEffect(() => {
    if (previousValue.current === value) {
      return;
    }

    previousValue.current = value;
    setIsChanged(true);

    const timer = window.setTimeout(() => {
      setIsChanged(false);
    }, 200);

    return () => {
      window.clearTimeout(timer);
    };
  }, [value]);

  return (
    <Card className={className}>
      <div
        className={cn(
          "space-y-2 transition-opacity duration-200",
          isChanged ? "opacity-70" : "opacity-100",
        )}
      >
        <p className="text-xs text-gray-500">{label}</p>
        <div className="flex items-baseline gap-2">
          <p className={cn("text-2xl font-semibold", toneClasses[tone])}>{value}</p>
          {trend ? <p className="text-xs text-gray-500">{trend}</p> : null}
        </div>
        {hint ? <p className="text-sm text-gray-500">{hint}</p> : null}
      </div>
    </Card>
  );
}
