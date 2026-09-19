export const SURFACES = ["Hard", "Clay", "Grass"] as const;
export type Surface = (typeof SURFACES)[number];

export type PlayerRecord = {
  id: number;
  name: string;
  country: string | null;
  hand: string | null;
  height: number | null;
  birthDate: string | null;
  age: number | null;
  rank: number | null;
  rankPoints: number | null;
  elo: number;
  played: number;
  eloHard: number;
  eloClay: number;
  eloGrass: number;
  playedHard: number;
  playedClay: number;
  playedGrass: number;
  formShort: number | null;
  formLong: number | null;
  formShortHard: number | null;
  formLongHard: number | null;
  formShortClay: number | null;
  formLongClay: number | null;
  formShortGrass: number | null;
  formLongGrass: number | null;
  serveWon: number | null;
  returnWon: number | null;
  lastMatch: string;
};

export type MatchContext = {
  surface: Surface;
  level: string;
  roundOrder: number;
  bestOf: number;
  drawSize: number;
  restDays: number;
  tourneyMatches: number;
};

export type HeadToHead = readonly [number, number];

export type Preset = {
  key: string;
  label: string;
  level: string;
  roundOrder: number;
  bestOf: number;
  drawSize: number;
};

export type Calibration =
  | { kind: "aucune" }
  | { kind: "platt"; coefficient: number; intercept: number }
  | { kind: "isotonique"; x: number[]; y: number[] };

export type SanityCase = {
  playerA: number;
  playerB: number;
  surface: Surface;
  preset: string;
  probability: number;
};

export type ModelMetadata = {
  file: string;
  features: string[];
  calibration: Calibration;
  presets: Preset[];
  neutralRestDays: number;
  trainedThrough: string;
  trees: number;
  parity: { rows: number; maxDifference: number; float32MaxDifference: number };
  sanity: SanityCase[];
};

export type PlayersPayload = {
  dataThrough: string;
  minMatches: number;
  reliableMatches: number;
  inactiveDays: number;
  columns: string[];
  players: unknown[][];
};

export type HeadToHeadPayload = {
  dataThrough: string;
  pairs: Record<string, [number, number, number][]>;
};
