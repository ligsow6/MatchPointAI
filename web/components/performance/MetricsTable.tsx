import { formatDecimal, formatPercent } from "@/lib/format";
import { METRICS } from "@/lib/models";
import type { ModelReport } from "@/lib/types";
import styles from "@/components/ui/DataTable.module.css";

function formatMetric(key: string, value: number): string {
  return key === "accuracy" ? formatPercent(value) : formatDecimal(value, 4);
}

function bestValue(
  models: ModelReport[],
  key: "accuracy" | "logLoss" | "brier" | "calibrationError",
): number {
  const values = models.map((model) => model[key]);
  return key === "accuracy" ? Math.max(...values) : Math.min(...values);
}

export function MetricsTable({ models }: { models: ModelReport[] }) {
  const columns = [
    ...METRICS.map((metric) => ({
      key: metric.key,
      label: metric.label,
      hint: metric.better === "higher" ? "plus haut = mieux" : "plus bas = mieux",
    })),
    { key: "calibrationError" as const, label: "Erreur de calibration", hint: "plus bas = mieux" },
  ];
  return (
    <div className={styles.scroll} tabIndex={0} role="region" aria-label="Tableau des métriques">
      <table className={styles.table}>
        <caption className="visually-hidden">
          Métriques sur la période de test ; la meilleure valeur de chaque colonne est en gras
        </caption>
        <thead>
          <tr>
            <th scope="col">Modèle</th>
            {columns.map((column) => (
              <th scope="col" key={column.key}>
                {column.label}
                <span className="visually-hidden"> ({column.hint})</span>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {models.map((model) => (
            <tr key={model.key}>
              <th scope="row">{model.label}</th>
              {columns.map((column) => {
                const value = model[column.key];
                const best = value === bestValue(models, column.key);
                return (
                  <td key={column.key} className={best ? styles.best : undefined}>
                    {column.key === "calibrationError"
                      ? formatPercent(value, 1)
                      : formatMetric(column.key, value)}
                    {best ? <span className="visually-hidden"> (meilleur)</span> : null}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
