"use client";

import {
  CartesianGrid,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { CalibrationBin } from "@/lib/types";
import { formatInteger, formatPercent } from "@/lib/format";
import { AXIS_TICK, CHART_COLORS } from "./theme";
import styles from "./Tooltip.module.css";

type Series = { key: string; label: string; color: string; bins: CalibrationBin[] };

type CalibrationPoint = { x: number; y: number; matches: number; series: string };

type TooltipProps = { active?: boolean; payload?: { payload: CalibrationPoint }[] };

function CalibrationTooltip({ active, payload }: TooltipProps) {
  const point = payload?.[0]?.payload;
  if (!active || !point) {
    return null;
  }
  return (
    <div className={styles.tooltip}>
      <p className={styles.heading}>{point.series}</p>
      <p>Probabilité prédite : {formatPercent(point.x)}</p>
      <p>Victoires observées : {formatPercent(point.y)}</p>
      <p className={styles.muted}>{formatInteger(point.matches)} matchs</p>
    </div>
  );
}

const TICKS = [0.5, 0.6, 0.7, 0.8, 0.9, 1];

export function CalibrationChart({ series, title }: { series: Series[]; title: string }) {
  return (
    <ResponsiveContainer width="100%" height={340}>
      <ScatterChart margin={{ top: 8, right: 16, bottom: 28, left: 4 }} title={title}>
        <CartesianGrid stroke={CHART_COLORS.grid} />
        <XAxis
          type="number"
          dataKey="x"
          domain={[0.5, 1]}
          ticks={TICKS}
          tickFormatter={(value: number) => formatPercent(value, 0)}
          tick={AXIS_TICK}
          stroke={CHART_COLORS.axis}
          label={{
            value: "Probabilité prédite pour le favori",
            position: "bottom",
            offset: 10,
            fill: "var(--text-2)",
            fontSize: 13,
          }}
        />
        <YAxis
          type="number"
          dataKey="y"
          domain={[0.45, 1]}
          ticks={[0.5, 0.6, 0.7, 0.8, 0.9, 1]}
          tickFormatter={(value: number) => formatPercent(value, 0)}
          tick={AXIS_TICK}
          stroke={CHART_COLORS.axis}
          width={48}
        />
        <ReferenceLine
          segment={[
            { x: 0.5, y: 0.5 },
            { x: 1, y: 1 },
          ]}
          stroke={CHART_COLORS.axis}
          strokeWidth={1.5}
          ifOverflow="hidden"
        />
        <Tooltip content={<CalibrationTooltip />} cursor={false} />
        {series.map((item) => (
          <Scatter
            key={item.key}
            name={item.label}
            data={item.bins.map((bin) => ({
              x: bin.predicted,
              y: bin.observed,
              matches: bin.matches,
              series: item.label,
            }))}
            fill={item.color}
            stroke={CHART_COLORS.surface}
            strokeWidth={2}
            line={{ stroke: item.color, strokeWidth: 2 }}
            isAnimationActive={false}
          />
        ))}
      </ScatterChart>
    </ResponsiveContainer>
  );
}
