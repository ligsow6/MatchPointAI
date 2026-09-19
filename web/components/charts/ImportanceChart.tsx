"use client";

import { Bar, BarChart, LabelList, ResponsiveContainer, XAxis, YAxis } from "recharts";
import { formatPercent } from "@/lib/format";
import type { FamilyShare } from "@/lib/types";
import { AXIS_TICK, CHART_COLORS } from "./theme";

export function ImportanceChart({ families, title }: { families: FamilyShare[]; title: string }) {
  const height = families.length * 44 + 16;
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart
        data={families}
        layout="vertical"
        margin={{ top: 0, right: 56, bottom: 0, left: 0 }}
        barCategoryGap={10}
        title={title}
      >
        <XAxis type="number" hide domain={[0, "dataMax"]} />
        <YAxis
          type="category"
          dataKey="label"
          width={150}
          tick={{ ...AXIS_TICK, fill: "var(--text-2)", fontSize: 12 }}
          tickLine={false}
          axisLine={false}
        />
        <Bar
          dataKey="share"
          fill={CHART_COLORS.model}
          radius={[0, 4, 4, 0]}
          maxBarSize={22}
          isAnimationActive={false}
        >
          <LabelList
            dataKey="share"
            position="right"
            formatter={(value: unknown) => formatPercent(Number(value), 1)}
            fill="var(--text-2)"
            fontSize={12}
          />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
