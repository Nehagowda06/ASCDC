import {
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { Card } from "../ui/Card";

export type TimelinePoint = {
  step: number;
  queueA: number;
  queueB: number;
  queueC: number;
  action: string;
  delayedEffects: string;
};

type TimelineProps = {
  points: TimelinePoint[];
};

export function Timeline({ points }: TimelineProps) {
  const recentPoints = points.slice(-6).reverse();

  return (
    <Card className="shadow-sm">
      <div className="space-y-4">
        <div className="space-y-1">
          <p className="text-xs font-medium uppercase tracking-[0.2em] text-gray-400">
            System Timeline
          </p>
          <p className="text-lg font-semibold text-gray-900">
            Queue levels, actions, and delayed effects over time
          </p>
        </div>

        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={points}>
              <XAxis
                axisLine={false}
                dataKey="step"
                tickLine={false}
                tick={{ fill: "#6b7280", fontSize: 12 }}
              />
              <YAxis
                axisLine={false}
                tickLine={false}
                tick={{ fill: "#6b7280", fontSize: 12 }}
              />
              <Tooltip
                contentStyle={{
                  borderRadius: 16,
                  borderColor: "#e5e7eb",
                  fontSize: 12,
                }}
              />
              <Line dataKey="queueA" dot={false} stroke="#2563eb" strokeWidth={2} type="monotone" />
              <Line dataKey="queueB" dot={false} stroke="#7c3aed" strokeWidth={2} type="monotone" />
              <Line dataKey="queueC" dot={false} stroke="#059669" strokeWidth={2} type="monotone" />
            </LineChart>
          </ResponsiveContainer>
        </div>

        <div className="grid gap-3 md:grid-cols-2">
          {recentPoints.map((point) => (
            <div key={`${point.step}-${point.action}`} className="rounded-2xl border border-gray-200 bg-gray-50 p-4">
              <div className="flex items-center justify-between">
                <p className="text-sm font-medium text-gray-900">Step {point.step}</p>
                <p className="text-xs text-gray-500">{point.action}</p>
              </div>
              <p className="mt-2 text-sm text-gray-500">
                Delayed effects: {point.delayedEffects || "None"}
              </p>
            </div>
          ))}
        </div>
      </div>
    </Card>
  );
}
