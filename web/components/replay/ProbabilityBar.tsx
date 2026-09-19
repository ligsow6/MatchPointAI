import { formatPercent } from "@/lib/format";
import { PLAYER_COLORS } from "./ReplayChart";
import styles from "./ReplayPlayer.module.css";

type ProbabilityBarProps = { names: readonly [string, string]; probability: number };

export function ProbabilityBar({ names, probability }: ProbabilityBarProps) {
  return (
    <div className={styles.probability}>
      <div className={styles.probabilityLabels}>
        <p>
          <span className={styles.probabilityName}>{names[0]}</span>
          <span className={styles.probabilityValue}>{formatPercent(probability)}</span>
        </p>
        <p className={styles.alignEnd}>
          <span className={styles.probabilityName}>{names[1]}</span>
          <span className={styles.probabilityValue}>{formatPercent(1 - probability)}</span>
        </p>
      </div>
      <div className={styles.track} aria-hidden="true">
        <span
          className={styles.fill}
          style={{ width: `${probability * 100}%`, background: PLAYER_COLORS[0] }}
        />
        <span
          className={styles.fill}
          style={{ width: `${(1 - probability) * 100}%`, background: PLAYER_COLORS[1] }}
        />
      </div>
    </div>
  );
}
