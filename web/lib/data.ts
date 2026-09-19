import { readFileSync } from "node:fs";
import path from "node:path";
import type { ModelMetadata, PlayersPayload } from "./comparator/types";
import type { ModelDetails, Overview, Performance, Replay, ReplaySummary } from "./types";

const PUBLIC_DIR = path.join(process.cwd(), "public");

function readPublicJson<T>(...segments: string[]): T {
  const content = readFileSync(path.join(PUBLIC_DIR, ...segments), "utf-8");
  return JSON.parse(content) as T;
}

function readJson<T>(...segments: string[]): T {
  return readPublicJson<T>("data", ...segments);
}

export function loadOverview(): Overview {
  return readJson<Overview>("overview.json");
}

export function loadPerformance(): Performance {
  return readJson<Performance>("performance.json");
}

export function loadModelDetails(): ModelDetails {
  return readJson<ModelDetails>("model.json");
}

export function loadReplayIndex(): ReplaySummary[] {
  return readJson<ReplaySummary[]>("replays", "index.json");
}

export function loadReplay(slug: string): Replay {
  const known = loadReplayIndex().some((replay) => replay.slug === slug);
  if (!known) {
    throw new Error(`Replay inconnu : ${slug}`);
  }
  return readJson<Replay>("replays", `${slug}.json`);
}

export type ComparatorSummary = {
  players: number;
  minMatches: number;
  reliableMatches: number;
  inactiveDays: number;
  metadata: ModelMetadata;
};

export function loadComparatorSummary(): ComparatorSummary {
  const payload = readJson<PlayersPayload>("players.json");
  return {
    players: payload.players.length,
    minMatches: payload.minMatches,
    reliableMatches: payload.reliableMatches,
    inactiveDays: payload.inactiveDays,
    metadata: readPublicJson<ModelMetadata>("model", "metadata.json"),
  };
}
