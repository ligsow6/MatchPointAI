import { formatSigned } from "@/lib/format";
import { METRICS } from "@/lib/models";
import type { Difference } from "@/lib/types";
import styles from "@/components/ui/DataTable.module.css";

function scaled(metric: string, value: number): string {
  return metric === "accuracy" ? `${formatSigned(value * 100, 1)} pts` : formatSigned(value, 4);
}

function improves(metric: string, value: number): boolean {
  return metric === "accuracy" ? value > 0 : value < 0;
}

export function ComparisonTable({
  differences,
  referenceLabel,
}: {
  differences: Difference[];
  referenceLabel: string;
}) {
  return (
    <div
      className={styles.scroll}
      tabIndex={0}
      role="region"
      aria-label={`Écarts face à ${referenceLabel}`}
    >
      <table className={styles.table}>
        <caption>LightGBM face à {referenceLabel}</caption>
        <thead>
          <tr>
            <th scope="col">Métrique</th>
            <th scope="col">Écart moyen</th>
            <th scope="col">Intervalle à 95 %</th>
            <th scope="col">Verdict</th>
          </tr>
        </thead>
        <tbody>
          {METRICS.map((metric) => {
            const difference = differences.find((item) => item.metric === metric.key);
            if (!difference) {
              return null;
            }
            const better = improves(metric.key, difference.mean);
            const verdict = difference.significant
              ? better
                ? "Amélioration significative"
                : "Dégradation significative"
              : "Pas de différence significative";
            return (
              <tr key={metric.key}>
                <th scope="row">{metric.label}</th>
                <td>{scaled(metric.key, difference.mean)}</td>
                <td>
                  [{scaled(metric.key, difference.lower)} ; {scaled(metric.key, difference.upper)}]
                </td>
                <td
                  className={
                    difference.significant
                      ? better
                        ? styles.positive
                        : styles.negative
                      : styles.muted
                  }
                >
                  {verdict}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
