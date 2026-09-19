import { formatDecimal, formatInteger, formatPercent, formatSigned } from "@/lib/format";
import type { Segment } from "@/lib/types";
import styles from "@/components/ui/DataTable.module.css";

export function SegmentsTable({ segments, title }: { segments: Segment[]; title: string }) {
  return (
    <div className={styles.scroll} tabIndex={0} role="region" aria-label={title}>
      <table className={styles.table}>
        <caption>{title}</caption>
        <thead>
          <tr>
            <th scope="col">Segment</th>
            <th scope="col">Matchs</th>
            <th scope="col">Exactitude Elo</th>
            <th scope="col">Exactitude LightGBM</th>
            <th scope="col">Écart</th>
            <th scope="col">Log loss Elo</th>
            <th scope="col">Log loss LightGBM</th>
          </tr>
        </thead>
        <tbody>
          {segments.map((segment) => {
            const gap = segment.model.accuracy - segment.elo.accuracy;
            return (
              <tr key={`${segment.dimension}-${segment.value}`}>
                <th scope="row">{segment.label}</th>
                <td>{formatInteger(segment.matches)}</td>
                <td>{formatPercent(segment.elo.accuracy)}</td>
                <td>{formatPercent(segment.model.accuracy)}</td>
                <td className={gap >= 0 ? styles.positive : styles.negative}>
                  {formatSigned(gap * 100, 1)} pts
                </td>
                <td>{formatDecimal(segment.elo.logLoss, 3)}</td>
                <td>{formatDecimal(segment.model.logLoss, 3)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
