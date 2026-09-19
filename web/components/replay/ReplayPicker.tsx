import Link from "next/link";
import type { ReplaySummary } from "@/lib/types";
import styles from "./ReplayPicker.module.css";

export function ReplayPicker({ replays, current }: { replays: ReplaySummary[]; current: string }) {
  return (
    <nav aria-label="Choisir un match" className={styles.picker}>
      <ul>
        {replays.map((replay) => (
          <li key={replay.slug}>
            <Link
              href={`/rejouer/${replay.slug}`}
              className={styles.card}
              aria-current={replay.slug === current ? "page" : undefined}
            >
              <span className={styles.title}>{replay.title}</span>
              <span className={styles.players}>
                {replay.shortNames[0]} – {replay.shortNames[1]}
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
