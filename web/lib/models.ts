import type {
  Comparison,
  Difference,
  MetricKey,
  ModelKey,
  ModelReport,
  Performance,
} from "./types";

export const METRICS: {
  key: MetricKey;
  label: string;
  better: "higher" | "lower";
  digits: number;
}[] = [
  { key: "accuracy", label: "Exactitude", better: "higher", digits: 1 },
  { key: "logLoss", label: "Log loss", better: "lower", digits: 3 },
  { key: "brier", label: "Brier", better: "lower", digits: 3 },
];

export function modelReport(performance: Performance, key: ModelKey): ModelReport {
  const report = performance.models.find((model) => model.key === key);
  if (!report) {
    throw new Error(`Modèle absent : ${key}`);
  }
  return report;
}

export function comparisonWith(
  performance: Performance,
  reference: Comparison["reference"],
): Difference[] {
  const comparison = performance.comparisons.find((item) => item.reference === reference);
  if (!comparison) {
    throw new Error(`Comparaison absente : ${reference}`);
  }
  return comparison.metrics;
}

export function differenceFor(differences: Difference[], metric: MetricKey): Difference {
  const difference = differences.find((item) => item.metric === metric);
  if (!difference) {
    throw new Error(`Métrique absente : ${metric}`);
  }
  return difference;
}
