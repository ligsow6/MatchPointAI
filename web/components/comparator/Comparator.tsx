"use client";

import { useEffect, useId, useMemo, useRef, useState } from "react";
import { ProbabilityBar } from "@/components/replay/ProbabilityBar";
import { PLAYER_COLORS } from "@/components/replay/ReplayChart";
import { loadRunner } from "@/lib/comparator/engine";
import {
  buildSearchIndex,
  contextFor,
  decodePlayers,
  eloProbability,
  headToHeadBetween,
  reliabilityIssues,
} from "@/lib/comparator/players";
import { predictMatch } from "@/lib/comparator/predict";
import {
  SURFACES,
  type HeadToHead,
  type HeadToHeadPayload,
  type ModelMetadata,
  type PlayerRecord,
  type PlayersPayload,
  type Surface,
} from "@/lib/comparator/types";
import { formatDate, formatPercent } from "@/lib/format";
import { PlayerCard } from "./PlayerCard";
import { PlayerCombobox } from "./PlayerCombobox";
import styles from "./Comparator.module.css";

const SURFACE_LABELS: Record<Surface, string> = {
  Hard: "Dur",
  Clay: "Terre battue",
  Grass: "Gazon",
};
const EXAMPLES: { players: [string, string]; surface: Surface; preset: string }[] = [
  { players: ["Jannik Sinner", "Carlos Alcaraz"], surface: "Clay", preset: "grand-chelem" },
  { players: ["Rafael Nadal", "Novak Djokovic"], surface: "Clay", preset: "grand-chelem" },
  { players: ["Roger Federer", "Bjorn Borg"], surface: "Grass", preset: "grand-chelem" },
  { players: ["Gael Monfils", "Arthur Fils"], surface: "Hard", preset: "atp" },
];

type Loaded = {
  players: PlayerRecord[];
  payload: PlayersPayload;
  pairs: HeadToHeadPayload;
  metadata: ModelMetadata;
};

type Result = {
  playerA: PlayerRecord;
  playerB: PlayerRecord;
  surface: Surface;
  presetLabel: string;
  probability: number;
  elo: number;
  headToHead: HeadToHead;
};

type Status =
  | { kind: "waiting" }
  | { kind: "loading-model" }
  | { kind: "ready"; result: Result }
  | { kind: "error"; message: string };

async function fetchJson<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`Impossible de charger ${url}`);
  }
  return (await response.json()) as T;
}

export function Comparator() {
  const [loaded, setLoaded] = useState<Loaded | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [playerA, setPlayerA] = useState<PlayerRecord | null>(null);
  const [playerB, setPlayerB] = useState<PlayerRecord | null>(null);
  const [surface, setSurface] = useState<Surface>("Hard");
  const [presetKey, setPresetKey] = useState("atp");
  const [status, setStatus] = useState<Status>({ kind: "waiting" });
  const request = useRef(0);
  const surfaceGroup = useId();
  const presetGroup = useId();

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      fetchJson<PlayersPayload>("/data/players.json"),
      fetchJson<HeadToHeadPayload>("/data/h2h.json"),
      fetchJson<ModelMetadata>("/model/metadata.json"),
    ])
      .then(([payload, pairs, metadata]) => {
        if (!cancelled) {
          setLoaded({ players: decodePlayers(payload), payload, pairs, metadata });
        }
      })
      .catch((error: unknown) => {
        if (!cancelled) {
          setLoadError(error instanceof Error ? error.message : "Chargement impossible");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const index = useMemo(() => (loaded ? buildSearchIndex(loaded.players) : null), [loaded]);
  const examples = useMemo(() => {
    if (!loaded) {
      return [];
    }
    const byName = new Map(loaded.players.map((player) => [player.name, player]));
    return EXAMPLES.flatMap((example) => {
      const first = byName.get(example.players[0]);
      const second = byName.get(example.players[1]);
      return first && second ? [{ ...example, first, second }] : [];
    });
  }, [loaded]);

  const run = async (
    nextA: PlayerRecord | null,
    nextB: PlayerRecord | null,
    nextSurface: Surface,
    nextPreset: string,
  ) => {
    const ticket = ++request.current;
    if (!loaded || !nextA || !nextB) {
      setStatus({ kind: "waiting" });
      return;
    }
    const preset = loaded.metadata.presets.find((item) => item.key === nextPreset);
    if (!preset) {
      return;
    }
    setStatus((current) => (current.kind === "ready" ? current : { kind: "loading-model" }));
    try {
      const runner = await loadRunner(`/model/${loaded.metadata.file}`);
      const headToHead = headToHeadBetween(loaded.pairs, nextA.id, nextB.id);
      const probability = await predictMatch(
        runner,
        loaded.metadata,
        nextA,
        nextB,
        contextFor(preset, nextSurface, loaded.metadata.neutralRestDays),
        headToHead,
      );
      if (ticket === request.current) {
        setStatus({
          kind: "ready",
          result: {
            playerA: nextA,
            playerB: nextB,
            surface: nextSurface,
            presetLabel: preset.label,
            probability,
            elo: eloProbability(nextA, nextB, nextSurface),
            headToHead,
          },
        });
      }
    } catch (error) {
      if (ticket === request.current) {
        setStatus({
          kind: "error",
          message: error instanceof Error ? error.message : "Calcul impossible",
        });
      }
    }
  };

  const update = (
    changes: Partial<{
      playerA: PlayerRecord | null;
      playerB: PlayerRecord | null;
      surface: Surface;
      preset: string;
    }>,
  ) => {
    const next = {
      playerA: "playerA" in changes ? (changes.playerA ?? null) : playerA,
      playerB: "playerB" in changes ? (changes.playerB ?? null) : playerB,
      surface: changes.surface ?? surface,
      preset: changes.preset ?? presetKey,
    };
    setPlayerA(next.playerA);
    setPlayerB(next.playerB);
    setSurface(next.surface);
    setPresetKey(next.preset);
    void run(next.playerA, next.playerB, next.surface, next.preset);
  };

  const thresholds = loaded
    ? {
        reliableMatches: loaded.payload.reliableMatches,
        inactiveDays: loaded.payload.inactiveDays,
        dataThrough: loaded.payload.dataThrough,
      }
    : null;
  const samePlayer = playerA !== null && playerB !== null && playerA.id === playerB.id;
  const result = status.kind === "ready" && !samePlayer ? status.result : null;
  const warnings =
    result && thresholds
      ? [result.playerA, result.playerB].flatMap((player) =>
          reliabilityIssues(player, thresholds).map((issue) => `${player.name} : ${issue}`),
        )
      : [];

  return (
    <div className={styles.comparator}>
      {loadError ? (
        <p className={styles.error} role="alert">
          {loadError}. Rechargez la page pour réessayer.
        </p>
      ) : null}

      <section aria-labelledby="choix-titre" className={styles.panel}>
        <h2 id="choix-titre" className={styles.panelTitle}>
          Choisir les joueurs
        </h2>
        <div className={styles.players}>
          <PlayerCombobox
            label="Joueur A"
            index={index}
            selected={playerA}
            onSelect={(player) => update({ playerA: player })}
            swatch={PLAYER_COLORS[0]}
          />
          <button
            type="button"
            className={styles.swap}
            onClick={() => update({ playerA: playerB, playerB: playerA })}
            disabled={!playerA && !playerB}
          >
            <span aria-hidden="true">⇄</span> Inverser
          </button>
          <PlayerCombobox
            label="Joueur B"
            index={index}
            selected={playerB}
            onSelect={(player) => update({ playerB: player })}
            swatch={PLAYER_COLORS[1]}
          />
        </div>
        {examples.length > 0 ? (
          <div className={styles.examples}>
            <p className={styles.examplesLabel}>Exemples</p>
            <ul>
              {examples.map((example) => (
                <li key={example.players.join("-")}>
                  <button
                    type="button"
                    className={styles.example}
                    onClick={() =>
                      update({
                        playerA: example.first,
                        playerB: example.second,
                        surface: example.surface,
                        preset: example.preset,
                      })
                    }
                  >
                    {example.first.name.split(" ").at(-1)} – {example.second.name.split(" ").at(-1)}
                    <span className={styles.exampleMeta}>{SURFACE_LABELS[example.surface]}</span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        ) : null}
        <div className={styles.contextRow}>
          <fieldset className={styles.segmented}>
            <legend>Surface</legend>
            <div className={styles.segments}>
              {SURFACES.map((item) => (
                <label key={item} className={styles.segment}>
                  <input
                    type="radio"
                    name={surfaceGroup}
                    value={item}
                    checked={surface === item}
                    onChange={() => update({ surface: item })}
                  />
                  <span>{SURFACE_LABELS[item]}</span>
                </label>
              ))}
            </div>
          </fieldset>
          <fieldset className={styles.segmented}>
            <legend>Type de tournoi</legend>
            <div className={styles.segments}>
              {(loaded?.metadata.presets ?? []).map((preset) => (
                <label key={preset.key} className={styles.segment}>
                  <input
                    type="radio"
                    name={presetGroup}
                    value={preset.key}
                    checked={presetKey === preset.key}
                    onChange={() => update({ preset: preset.key })}
                  />
                  <span>{preset.label}</span>
                </label>
              ))}
            </div>
          </fieldset>
        </div>
      </section>

      <section aria-labelledby="resultat-titre" className={styles.panel}>
        <h2 id="resultat-titre" className={styles.panelTitle}>
          Probabilité de victoire
        </h2>
        <div aria-live="polite" aria-busy={status.kind === "loading-model"}>
          {samePlayer ? (
            <p className={styles.placeholder}>Choisissez deux joueurs différents.</p>
          ) : status.kind === "loading-model" ? (
            <p className={styles.placeholder}>
              Chargement du modèle dans votre navigateur (environ 3 Mo, une seule fois)…
            </p>
          ) : status.kind === "error" ? (
            <p className={styles.error}>Le calcul a échoué : {status.message}.</p>
          ) : result ? (
            <div className={styles.result}>
              <p className="visually-hidden">
                {result.playerA.name} {formatPercent(result.probability)}, {result.playerB.name}{" "}
                {formatPercent(1 - result.probability)}.
              </p>
              <div aria-hidden="true">
                <ProbabilityBar
                  names={[result.playerA.name, result.playerB.name]}
                  probability={result.probability}
                />
              </div>
              <p className={styles.resultMeta}>
                {SURFACE_LABELS[result.surface]} · {result.presetLabel} · Elo par surface seul :{" "}
                {formatPercent(result.elo)} pour {result.playerA.name.split(" ").at(-1)}
              </p>
              <p className={styles.resultMeta}>
                {result.headToHead[0] + result.headToHead[1] > 0
                  ? `Face-à-face dans la base : ${result.headToHead[0]} – ${result.headToHead[1]}.`
                  : "Ces deux joueurs ne se sont jamais affrontés dans la base."}
              </p>
              {warnings.length > 0 ? (
                <div className={styles.warning}>
                  <p className={styles.warningTitle}>
                    <span aria-hidden="true">⚠</span> Estimation peu fiable — historique insuffisant
                    ou joueur inactif.
                  </p>
                  <ul>
                    {warnings.map((warning) => (
                      <li key={warning}>{warning}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
            </div>
          ) : (
            <p className={styles.placeholder}>
              Choisissez deux joueurs : le calcul se lance automatiquement, directement dans votre
              navigateur.
            </p>
          )}
        </div>
        {result && thresholds ? (
          <div className={styles.cards}>
            <PlayerCard
              player={result.playerA}
              surface={result.surface}
              color={PLAYER_COLORS[0]}
              dataThrough={thresholds.dataThrough}
            />
            <PlayerCard
              player={result.playerB}
              surface={result.surface}
              color={PLAYER_COLORS[1]}
              dataThrough={thresholds.dataThrough}
            />
          </div>
        ) : null}
      </section>
      {loaded ? (
        <p className={styles.footnote}>
          Chaque joueur est pris tel qu&apos;il était à l&apos;issue de son dernier match connu
          (données jusqu&apos;au {formatDate(loaded.payload.dataThrough)}). Le match imaginé est un
          premier tour, les deux joueurs arrivant reposés ({loaded.metadata.neutralRestDays} jours
          depuis leur dernier match).
        </p>
      ) : null}
    </div>
  );
}
