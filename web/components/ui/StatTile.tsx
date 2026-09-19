import type { ReactNode } from "react";
import styles from "./StatTile.module.css";

type StatTileProps = {
  label: string;
  value: string;
  detail?: ReactNode;
  emphasis?: boolean;
};

export function StatTile({ label, value, detail, emphasis = false }: StatTileProps) {
  return (
    <div className={`${styles.tile} ${emphasis ? styles.emphasis : ""}`}>
      <dt className={styles.label}>{label}</dt>
      <dd className={styles.value}>{value}</dd>
      {detail ? <dd className={styles.detail}>{detail}</dd> : null}
    </div>
  );
}

export function StatGrid({ children }: { children: ReactNode }) {
  return <dl className={styles.grid}>{children}</dl>;
}
