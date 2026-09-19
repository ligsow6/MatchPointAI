"use client";

import { memo, useMemo } from "react";
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceDot,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { AXIS_TICK, CHART_COLORS } from "@/components/charts/theme";
import tooltipStyles from "@/components/charts/Tooltip.module.css";
import { formatPercent } from "@/lib/format";
import type { Replay } from "@/lib/types";
import { setBoundaries } from "./replayState";

export const PLAYER_COLORS = ["var(--series-model)", "var(--series-elo)"] as const;
const PLAYER_WASHES = ["var(--wash-model)", "var(--wash-elo)"] as const;

type Row = {
  index: number;
  probability: number;
  above: [number, number];
  below: [number, number];
  label: string;
};

function describe(replay: Replay, index: number): string {
  const point = replay.timeline[index - 1];
  if (!point) {
    return "Avant le match";
  }
  const pointScore = point.tiebreak
    ? `tie-break ${point.points[0]}-${point.points[1]}`
    : `${point.points[0]}-${point.points[1]}`;
  return `Point ${index} · sets ${point.sets[0]}-${point.sets[1]} · jeux ${point.games[0]}-${point.games[1]} · ${pointScore}`;
}

function buildRows(replay: Replay): Row[] {
  const probabilities = [replay.preMatch.model, ...replay.timeline.map((point) => point.p)];
  return probabilities.map((probability, index) => ({
    index,
    probability,
    above: [0.5, Math.max(probability, 0.5)],
    below: [Math.min(probability, 0.5), 0.5],
    label: describe(replay, index),
  }));
}

type TooltipProps = { active?: boolean; payload?: { payload: Row }[]; names: readonly string[] };

function PointTooltip({ active, payload, names }: TooltipProps) {
  const row = payload?.[0]?.payload;
  if (!active || !row) {
    return null;
  }
  return (
    <div className={tooltipStyles.tooltip}>
      <p className={tooltipStyles.heading}>{row.label}</p>
      <p className={tooltipStyles.row}>
        <span className={tooltipStyles.key} style={{ background: PLAYER_COLORS[0] }} />
        {names[0]} : {formatPercent(row.probability)}
      </p>
      <p className={tooltipStyles.row}>
        <span className={tooltipStyles.key} style={{ background: PLAYER_COLORS[1] }} />
        {names[1]} : {formatPercent(1 - row.probability)}
      </p>
    </div>
  );
}

type ReplayChartProps = {
  replay: Replay;
  visible: number;
  savedMatchPoints: number[];
};

function ReplayChartComponent({ replay, visible, savedMatchPoints }: ReplayChartProps) {
  const rows = useMemo(() => buildRows(replay), [replay]);
  const boundaries = useMemo(() => setBoundaries(replay), [replay]);
  const shown = rows.slice(0, visible + 1);
  const current = rows[visible];
  const total = replay.timeline.length;
  return (
    <ResponsiveContainer width="100%" height={360}>
      <ComposedChart
        data={shown}
        margin={{ top: 28, right: 12, bottom: 8, left: 4 }}
        title={`Probabilité de victoire de ${replay.shortNames[0]} au fil des points`}
      >
        <CartesianGrid stroke={CHART_COLORS.grid} vertical={false} />
        <XAxis
          type="number"
          dataKey="index"
          domain={[0, total]}
          allowDataOverflow
          tick={AXIS_TICK}
          stroke={CHART_COLORS.axis}
          tickCount={6}
          tickMargin={6}
        />
        <YAxis
          type="number"
          domain={[0, 1]}
          ticks={[0, 0.25, 0.5, 0.75, 1]}
          tickFormatter={(value: number) => formatPercent(value, 0)}
          tick={AXIS_TICK}
          stroke={CHART_COLORS.axis}
          width={48}
        />
        {boundaries
          .filter((boundary) => boundary.index <= visible)
          .map((boundary) => (
            <ReferenceLine
              key={boundary.index}
              x={boundary.index}
              stroke={CHART_COLORS.axis}
              strokeWidth={1}
              label={{
                value: boundary.label,
                position: "top",
                fill: "var(--muted)",
                fontSize: 11,
              }}
            />
          ))}
        <ReferenceLine y={0.5} stroke={CHART_COLORS.axis} strokeWidth={1} />
        <Area
          dataKey="above"
          stroke="none"
          fill={PLAYER_WASHES[0]}
          fillOpacity={1}
          isAnimationActive={false}
          activeDot={false}
        />
        <Area
          dataKey="below"
          stroke="none"
          fill={PLAYER_WASHES[1]}
          fillOpacity={1}
          isAnimationActive={false}
          activeDot={false}
        />
        <Line
          dataKey="probability"
          stroke={CHART_COLORS.ink}
          strokeWidth={2}
          dot={false}
          activeDot={{ r: 5, fill: CHART_COLORS.ink, stroke: CHART_COLORS.surface, strokeWidth: 2 }}
          isAnimationActive={false}
        />
        {savedMatchPoints
          .filter((index) => index <= visible)
          .map((index) => (
            <ReferenceDot
              key={`saved-${index}`}
              x={index}
              y={rows[index]?.probability ?? 0.5}
              r={5}
              fill="var(--negative)"
              stroke={CHART_COLORS.surface}
              strokeWidth={2}
            />
          ))}
        {current ? (
          <ReferenceDot
            x={current.index}
            y={current.probability}
            r={6}
            fill={current.probability >= 0.5 ? PLAYER_COLORS[0] : PLAYER_COLORS[1]}
            stroke={CHART_COLORS.surface}
            strokeWidth={2}
          />
        ) : null}
        <Tooltip
          content={<PointTooltip names={replay.shortNames} />}
          cursor={{ stroke: CHART_COLORS.axis, strokeWidth: 1 }}
          isAnimationActive={false}
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}

export const ReplayChart = memo(ReplayChartComponent);
