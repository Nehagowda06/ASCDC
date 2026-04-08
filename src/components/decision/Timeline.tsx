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
  const chartPoints =
    points.length >= 2
      ? points
      : points.length === 1
        ? [
            {
              ...points[0],
              step: Math.max(0, points[0].step - 1),
              action: "PREVIOUS",
            },
            points[0],
          ]
        : [
            {
              step: 0,
              queueA: 0,
              queueB: 0,
              queueC: 0,
              action: "START",
              delayedEffects: "",
            },
            {
              step: 1,
              queueA: 0,
              queueB: 0,
              queueC: 0,
              action: "START",
              delayedEffects: "",
            },
          ];

  const recentPoints = chartPoints.slice(-6).reverse();

  return (
    <Card className="bg-[#14181f] text-gray-100 shadow-sm">
      <div className="space-y-4">
        <div className="space-y-1">
          <p className="text-[11px] font-medium uppercase tracking-[0.16em] text-gray-400">
            System Timeline
          </p>
          <p className="text-base font-semibold text-white">
            Queue levels, actions, and delayed effects over time
          </p>
        </div>

        <div className="h-72">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartPoints}>
              <XAxis
                axisLine={false}
                dataKey="step"
                tickLine={false}
                tick={{ fill: "#9ca3af", fontSize: 11 }}
              />
              <YAxis
                axisLine={false}
                tickLine={false}
                tick={{ fill: "#9ca3af", fontSize: 11 }}
              />
              <Tooltip
                contentStyle={{
                  borderRadius: 14,
                  borderColor: "#313845",
                  backgroundColor: "#171c24",
                  color: "#f3f4f6",
                  fontSize: 11,
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
              <div key={`${point.step}-${point.action}`} className="rounded-xl border border-[#2a3039] bg-[#171c24] p-4">
              <div className="flex items-center justify-between">
                <p className="text-[13px] font-medium text-white">Step {point.step}</p>
                <p className="text-[11px] uppercase tracking-[0.12em] text-gray-500">{point.action}</p>
              </div>
              <p className="mt-2 text-[13px] leading-6 text-gray-400">
                Delayed effects: {point.delayedEffects || "None"}
              </p>
            </div>
          ))}
        </div>
      </div>
    </Card>
  );
}
