import type { ReactNode } from "react";
import styles from "./ChartFigure.module.css";

type ChartFigureProps = {
  title: string;
  description: string;
  legend?: ReactNode;
  controls?: ReactNode;
  table: ReactNode;
  children: ReactNode;
};

export function ChartFigure({
  title,
  description,
  legend,
  controls,
  table,
  children,
}: ChartFigureProps) {
  return (
    <figure className={styles.figure}>
      <figcaption className={styles.caption}>
        <span className={styles.title}>{title}</span>
        <span className={styles.description}>{description}</span>
      </figcaption>
      {controls}
      {legend}
      <div className={styles.plot}>{children}</div>
      <details className={styles.details}>
        <summary>Voir les données sous forme de tableau</summary>
        <div className={styles.tableWrapper}>{table}</div>
      </details>
    </figure>
  );
}

export type LegendItem = { label: string; color: string; shape?: "line" | "dot" };

export function ChartLegend({ items }: { items: LegendItem[] }) {
  return (
    <ul className={styles.legend} aria-label="Légende">
      {items.map((item) => (
        <li key={item.label}>
          <span
            aria-hidden="true"
            className={item.shape === "dot" ? styles.dot : styles.line}
            style={{ background: item.color }}
          />
          {item.label}
        </li>
      ))}
    </ul>
  );
}
