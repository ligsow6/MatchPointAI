import type { ReactNode } from "react";
import styles from "./Section.module.css";

type SectionProps = {
  id: string;
  title: string;
  lead?: ReactNode;
  children: ReactNode;
};

export function Section({ id, title, lead, children }: SectionProps) {
  const headingId = `${id}-titre`;
  return (
    <section id={id} aria-labelledby={headingId} className={styles.section}>
      <h2 id={headingId}>{title}</h2>
      {lead ? <div className={styles.lead}>{lead}</div> : null}
      {children}
    </section>
  );
}

export function PageIntro({
  eyebrow,
  title,
  children,
}: {
  eyebrow: string;
  title: string;
  children: ReactNode;
}) {
  return (
    <header className={styles.intro}>
      <p className={styles.eyebrow}>{eyebrow}</p>
      <h1>{title}</h1>
      <div className={styles.introText}>{children}</div>
    </header>
  );
}

export function Callout({ title, children }: { title: string; children: ReactNode }) {
  return (
    <aside className={styles.callout} aria-label={title}>
      <p className={styles.calloutTitle}>{title}</p>
      {children}
    </aside>
  );
}
