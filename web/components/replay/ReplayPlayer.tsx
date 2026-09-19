"use client";

import {
  useCallback,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  useSyncExternalStore,
} from "react";
import { ChartLegend } from "@/components/charts/ChartFigure";
import tableStyles from "@/components/ui/DataTable.module.css";
import { formatDate, formatPercent } from "@/lib/format";
import type { Replay } from "@/lib/types";
import { ProbabilityBar } from "./ProbabilityBar";
import { PLAYER_COLORS, ReplayChart } from "./ReplayChart";
import {
  POINTS_PER_SECOND_AT_1X,
  SPEEDS,
  eventAnnouncement,
  gameRows,
  scoreSentence,
  snapshotAt,
} from "./replayState";
import { Scoreboard } from "./Scoreboard";
import styles from "./ReplayPlayer.module.css";

type Speed = (typeof SPEEDS)[number];

const REDUCED_MOTION_QUERY = "(prefers-reduced-motion: reduce)";

function subscribeToMotionPreference(onChange: () => void): () => void {
  const media = window.matchMedia(REDUCED_MOTION_QUERY);
  media.addEventListener("change", onChange);
  return () => media.removeEventListener("change", onChange);
}

function useReducedMotion(): boolean {
  return useSyncExternalStore(
    subscribeToMotionPreference,
    () => window.matchMedia(REDUCED_MOTION_QUERY).matches,
    () => false,
  );
}

export function ReplayPlayer({ replay }: { replay: Replay }) {
  const total = replay.timeline.length;
  const [index, setIndex] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState<Speed>(4);
  const [announcement, setAnnouncement] = useState("");
  const reducedMotion = useReducedMotion();
  const progress = useRef(0);
  const speedId = useId();
  const scrubberId = useId();

  const snapshot = useMemo(() => snapshotAt(replay, index), [replay, index]);
  const loser = replay.winner === 0 ? 1 : 0;
  const savedMatchPoints = useMemo(
    () =>
      replay.timeline
        .map((point, position) => ({ point, index: position + 1 }))
        .filter(
          ({ point }) =>
            point.opportunities.includes(`match_point_${loser}`) && point.winner === replay.winner,
        )
        .map((item) => item.index),
    [replay, loser],
  );
  const rows = useMemo(() => gameRows(replay), [replay]);

  const goTo = useCallback(
    (target: number) => {
      const bounded = Math.min(Math.max(target, 0), total);
      progress.current = bounded;
      setIndex(bounded);
    },
    [total],
  );

  useEffect(() => {
    if (!playing) {
      return;
    }
    let frame = 0;
    let previous: number | null = null;
    const step = (timestamp: number) => {
      const elapsed = previous === null ? 0 : timestamp - previous;
      previous = timestamp;
      const before = Math.floor(progress.current);
      progress.current = Math.min(
        progress.current + (elapsed / 1000) * POINTS_PER_SECOND_AT_1X * speed,
        total,
      );
      const after = Math.floor(progress.current);
      if (after !== before) {
        setIndex(after);
        for (let reached = before + 1; reached <= after; reached += 1) {
          const point = replay.timeline[reached - 1];
          const message = point ? eventAnnouncement(replay, point) : null;
          if (message) {
            setAnnouncement(message);
          }
        }
      }
      if (progress.current >= total) {
        setPlaying(false);
        return;
      }
      frame = window.requestAnimationFrame(step);
    };
    frame = window.requestAnimationFrame(step);
    return () => window.cancelAnimationFrame(frame);
  }, [playing, speed, total, replay]);

  const togglePlay = () => {
    if (!playing && index >= total) {
      goTo(0);
    }
    setPlaying((value) => !value);
  };

  const restart = () => {
    setPlaying(false);
    goTo(0);
    setAnnouncement("Replay remis au début.");
  };

  const seek = (target: number) => {
    setPlaying(false);
    goTo(target);
  };

  const jumpTo = (target: number) => {
    setPlaying(false);
    goTo(target);
    setAnnouncement(scoreSentence(replay, snapshotAt(replay, target)));
  };

  const [first, second] = replay.shortNames;
  const favorite = replay.preMatch.model >= 0.5 ? 0 : 1;
  const favoriteChance = favorite === 0 ? replay.preMatch.model : 1 - replay.preMatch.model;
  const eloChance = favorite === 0 ? replay.preMatch.elo : 1 - replay.preMatch.elo;
  const upset = favorite !== replay.winner;
  const playLabel = playing
    ? "Pause"
    : index >= total
      ? "Revoir"
      : index > 0
        ? "Reprendre"
        : "Lancer le replay";

  return (
    <article className={styles.player} aria-labelledby="replay-titre">
      <header className={styles.header}>
        <div>
          <h2 id="replay-titre">{replay.title}</h2>
          <p className={styles.meta}>
            {formatDate(replay.date)} · {replay.surface} · {replay.points} points rejoués
          </p>
        </div>
        <p className={styles.result}>
          <strong>
            {replay.shortNames[replay.winner]} bat {replay.shortNames[replay.winner === 0 ? 1 : 0]}
          </strong>{" "}
          {replay.score}
        </p>
      </header>

      <p className={styles.preMatch}>
        Avant le match, LightGBM donnait{" "}
        <strong>
          {formatPercent(favoriteChance)} à {replay.shortNames[favorite]}
        </strong>{" "}
        (Elo : {formatPercent(eloChance)}).{" "}
        {upset
          ? "Le favori du modèle a perdu : un rappel qu'une probabilité n'est pas une certitude."
          : "Le favori du modèle l'a emporté."}
      </p>

      <div className={styles.board}>
        <Scoreboard replay={replay} snapshot={snapshot} />
        <ProbabilityBar names={replay.shortNames} probability={snapshot.probability} />
      </div>

      <div className={styles.chartCard}>
        <ChartLegend
          items={[
            { label: `Zone où ${first} est favori`, color: PLAYER_COLORS[0], shape: "dot" },
            { label: `Zone où ${second} est favori`, color: PLAYER_COLORS[1], shape: "dot" },
            ...(savedMatchPoints.length > 0
              ? [
                  {
                    label: "Balle de match sauvée",
                    color: "var(--negative)",
                    shape: "dot" as const,
                  },
                ]
              : []),
          ]}
        />
        <p className={styles.axisNote}>
          Probabilité que {first} gagne le match après chaque point (axe horizontal : numéro du
          point). Les traits verticaux marquent la fin de chaque set.
        </p>
        <ReplayChart replay={replay} visible={index} savedMatchPoints={savedMatchPoints} />
      </div>

      <div className={styles.controls} role="group" aria-label="Contrôles du replay">
        <button type="button" className={styles.primaryButton} onClick={togglePlay}>
          <svg aria-hidden="true" viewBox="0 0 20 20" width="18" height="18" focusable="false">
            {playing ? (
              <path d="M5 3.5h3.5v13H5zM11.5 3.5H15v13h-3.5z" fill="currentColor" />
            ) : (
              <path
                d="M6 3.8v12.4a.8.8 0 0 0 1.2.7l9.8-6.2a.8.8 0 0 0 0-1.4L7.2 3.1A.8.8 0 0 0 6 3.8Z"
                fill="currentColor"
              />
            )}
          </svg>
          {playLabel}
        </button>
        <button
          type="button"
          className={styles.button}
          onClick={() => jumpTo(index - 1)}
          disabled={index === 0}
        >
          <span aria-hidden="true">←</span> Point précédent
        </button>
        <button
          type="button"
          className={styles.button}
          onClick={() => jumpTo(index + 1)}
          disabled={index >= total}
        >
          Point suivant <span aria-hidden="true">→</span>
        </button>
        <button type="button" className={styles.button} onClick={restart} disabled={index === 0}>
          Recommencer
        </button>
        <label className={styles.speed} htmlFor={speedId}>
          Vitesse
          <select
            id={speedId}
            value={speed}
            onChange={(event) => setSpeed(Number(event.target.value) as Speed)}
          >
            {SPEEDS.map((value) => (
              <option key={value} value={value}>
                {value}×
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className={styles.scrubber}>
        <label htmlFor={scrubberId}>Position dans le match</label>
        <input
          id={scrubberId}
          type="range"
          min={0}
          max={total}
          step={1}
          value={index}
          onChange={(event) => seek(Number(event.target.value))}
          aria-valuetext={scoreSentence(replay, snapshot)}
        />
        <p className={styles.scrubberText} aria-hidden="true">
          {index === 0 ? "Avant le premier point" : `Point ${index} / ${total}`}
        </p>
      </div>

      <p className="visually-hidden" aria-live="polite" aria-atomic="true">
        {announcement}
      </p>
      {reducedMotion ? (
        <p className={styles.motionNote}>
          Animations réduites : utilisez les boutons « Point suivant » ou le curseur pour avancer à
          votre rythme.
        </p>
      ) : null}

      {replay.moments.length > 0 ? (
        <section className={styles.moments} aria-labelledby="moments-titre">
          <h3 id="moments-titre">Moments clés</h3>
          <ol>
            {replay.moments.map((moment) => (
              <li key={`${moment.n}-${moment.kind}-${moment.text}`}>
                <button
                  type="button"
                  className={styles.momentButton}
                  onClick={() => jumpTo(moment.n)}
                  aria-current={index === moment.n ? "step" : undefined}
                >
                  <span className={styles.momentPoint}>Point {moment.n}</span>
                  <span>{moment.text}</span>
                </button>
              </li>
            ))}
          </ol>
        </section>
      ) : null}

      <details className={styles.details}>
        <summary>Voir l&apos;évolution jeu par jeu sous forme de tableau</summary>
        <div
          className={tableStyles.scroll}
          tabIndex={0}
          role="region"
          aria-label="Évolution jeu par jeu"
        >
          <table className={tableStyles.table}>
            <thead>
              <tr>
                <th scope="col">Après le point</th>
                <th scope="col">Sets</th>
                <th scope="col">Jeux</th>
                <th scope="col">Chances de {first}</th>
                <th scope="col">Chances de {second}</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(({ index: pointIndex, point }) => (
                <tr key={pointIndex}>
                  <th scope="row">{pointIndex}</th>
                  <td>
                    {point.sets[0]}-{point.sets[1]}
                  </td>
                  <td>
                    {point.games[0]}-{point.games[1]}
                  </td>
                  <td>{formatPercent(point.p)}</td>
                  <td>{formatPercent(1 - point.p)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </article>
  );
}
