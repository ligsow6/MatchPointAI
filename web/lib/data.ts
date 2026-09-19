import { readFileSync } from "node:fs";
import path from "node:path";
import type { ModelDetails, Overview, Performance, Replay, ReplaySummary } from "./types";

const DATA_DIR = path.join(process.cwd(), "public", "data");

function readJson<T>(...segments: string[]): T {
  const content = readFileSync(path.join(DATA_DIR, ...segments), "utf-8");
  return JSON.parse(content) as T;
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
