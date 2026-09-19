"use client";

import { useId, useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { formatDecimal, formatInteger, formatPercent } from "@/lib/format";
import type { MetricKey, YearResult } from "@/lib/types";
import { AXIS_TICK, CHART_COLORS } from "./theme";
import styles from "./YearlyChart.module.css";
import tooltipStyles from "./Tooltip.module.css";

const OPTIONS: { key: MetricKey; label: string; hint: string }[] = [
  { key: "accuracy", label: "Exactitude", hint: "plus haut = mieux" },
  { key: "logLoss", label: "Log loss", hint: "plus bas = mieux" },
  { key: "brier", label: "Brier", hint: "plus bas = mieux" },
];

function formatMetric(metric: MetricKey, value: number): string {
  return metric === "accuracy" ? formatPercent(value) : formatDecimal(value, 3);
}

type Row = { year: number; matches: number; model: number; elo: number };

type TooltipProps = {
  active?: boolean;
  payload?: { payload: Row }[];
  metric: MetricKey;
  labels: { model: string; elo: string };
};

function YearTooltip({ active, payload, metric, labels }: TooltipProps) {
  const row = payload?.[0]?.payload;
  if (!active || !row) {
    return null;
  }
  return (
    <div className={tooltipStyles.tooltip}>
      <p className={tooltipStyles.heading}>{row.year}</p>
      <p className={tooltipStyles.row}>
        <span className={tooltipStyles.key} style={{ background: CHART_COLORS.model }} />
        {labels.model} : {formatMetric(metric, row.model)}
      </p>
      <p className={tooltipStyles.row}>
        <span className={tooltipStyles.key} style={{ background: CHART_COLORS.elo }} />
        {labels.elo} : {formatMetric(metric, row.elo)}
      </p>
      <p className={tooltipStyles.muted}>{formatInteger(row.matches)} matchs</p>
    </div>
  );
}

type YearlyChartProps = {
  years: YearResult[];
  labels: { model: string; elo: string };
};

export function YearlyChart({ years, labels }: YearlyChartProps) {
  const [metric, setMetric] = useState<MetricKey>("logLoss");
  const groupName = useId();
  const rows: Row[] = years.map((year) => ({
    year: year.year,
    matches: year.matches,
    model: year.model[metric],
    elo: year.elo[metric],
  }));
  const selected = OPTIONS.find((option) => option.key === metric) ?? OPTIONS[1];
  return (
    <div>
      <fieldset className={styles.switcher}>
        <legend className={styles.legendText}>Métrique affichée</legend>
        <div className={styles.options}>
          {OPTIONS.map((option) => (
            <label key={option.key} className={styles.option}>
              <input
                type="radio"
                name={groupName}
                value={option.key}
                checked={metric === option.key}
                onChange={() => setMetric(option.key)}
              />
              <span>{option.label}</span>
            </label>
          ))}
        </div>
      </fieldset>
      <p className={styles.hint} aria-live="polite">
        {selected?.label} par saison, {selected?.hint}.
      </p>
      <ResponsiveContainer width="100%" height={320}>
        <LineChart
          data={rows}
          margin={{ top: 8, right: 16, bottom: 4, left: 4 }}
          title={`${selected?.label} par saison`}
        >
          <CartesianGrid stroke={CHART_COLORS.grid} vertical={false} />
          <XAxis
            dataKey="year"
            tick={AXIS_TICK}
            stroke={CHART_COLORS.axis}
            tickMargin={8}
            minTickGap={16}
          />
          <YAxis
            domain={["auto", "auto"]}
            tickFormatter={(value: number) =>
              metric === "accuracy" ? formatPercent(value, 0) : formatDecimal(value, 2)
            }
            tick={AXIS_TICK}
            stroke={CHART_COLORS.axis}
            width={52}
          />
          <Tooltip
            content={<YearTooltip metric={metric} labels={labels} />}
            cursor={{ stroke: CHART_COLORS.axis, strokeWidth: 1 }}
          />
          <Line
            type="monotone"
            dataKey="elo"
            name={labels.elo}
            stroke={CHART_COLORS.elo}
            strokeWidth={2}
            dot={{ r: 3, fill: CHART_COLORS.elo, stroke: CHART_COLORS.surface, strokeWidth: 2 }}
            activeDot={{ r: 5, stroke: CHART_COLORS.surface, strokeWidth: 2 }}
            isAnimationActive={false}
          />
          <Line
            type="monotone"
            dataKey="model"
            name={labels.model}
            stroke={CHART_COLORS.model}
            strokeWidth={2}
            dot={{ r: 3, fill: CHART_COLORS.model, stroke: CHART_COLORS.surface, strokeWidth: 2 }}
            activeDot={{ r: 5, stroke: CHART_COLORS.surface, strokeWidth: 2 }}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
