import { daysSinceLastMatch } from "@/lib/comparator/players";
import type { PlayerRecord, Surface } from "@/lib/comparator/types";
import { formatDate, formatDecimal, formatInteger, formatPercent } from "@/lib/format";
import styles from "./Comparator.module.css";

type PlayerCardProps = {
  player: PlayerRecord;
  surface: Surface;
  color: string;
  dataThrough: string;
};

const SURFACE_NAMES: Record<Surface, string> = {
  Hard: "le dur",
  Clay: "la terre battue",
  Grass: "le gazon",
};

function percent(value: number | null): string {
  return value === null ? "—" : formatPercent(value, 0);
}

export function PlayerCard({ player, surface, color, dataThrough }: PlayerCardProps) {
  const surfaceElo = { Hard: player.eloHard, Clay: player.eloClay, Grass: player.eloGrass }[
    surface
  ];
  const surfacePlayed = {
    Hard: player.playedHard,
    Clay: player.playedClay,
    Grass: player.playedGrass,
  }[surface];
  const surfaceForm = {
    Hard: player.formShortHard,
    Clay: player.formShortClay,
    Grass: player.formShortGrass,
  }[surface];
  const days = daysSinceLastMatch(player, dataThrough);
  const rows: [string, string][] = [
    ["Elo global", formatDecimal(player.elo, 0)],
    [`Elo sur ${SURFACE_NAMES[surface]}`, formatDecimal(surfaceElo, 0)],
    [
      "Matchs dans la base",
      `${formatInteger(player.played)} (${formatInteger(surfacePlayed)} sur la surface)`,
    ],
    ["Victoires sur les 10 derniers matchs", percent(player.formShort)],
    [`Victoires sur les 10 derniers sur ${SURFACE_NAMES[surface]}`, percent(surfaceForm)],
    ["Points gagnés au service", percent(player.serveWon)],
    ["Points gagnés au retour", percent(player.returnWon)],
    [
      "Classement au dernier match",
      player.rank === null ? "non classé" : `${formatInteger(player.rank)}e`,
    ],
    ["Âge au dernier match", player.age === null ? "—" : `${formatDecimal(player.age, 1)} ans`],
    [
      "Dernier match",
      `${formatDate(player.lastMatch)}${days > 0 ? ` (${formatInteger(days)} jours avant la fin des données)` : ""}`,
    ],
  ];
  return (
    <article className={styles.card} aria-label={`Profil de ${player.name}`}>
      <h3 className={styles.cardTitle}>
        <span className={styles.swatch} style={{ background: color }} aria-hidden="true" />
        {player.name}
        {player.country ? <span className={styles.country}>{player.country}</span> : null}
      </h3>
      <dl className={styles.stats}>
        {rows.map(([label, value]) => (
          <div key={label}>
            <dt>{label}</dt>
            <dd>{value}</dd>
          </div>
        ))}
      </dl>
    </article>
  );
}
