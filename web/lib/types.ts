export type ModelKey = "elo" | "elo_recalibrated" | "model";
export type MetricKey = "accuracy" | "logLoss" | "brier";

export type Scores = {
  matches: number;
  accuracy: number;
  logLoss: number;
  brier: number;
  calibrationError: number;
};

export type CalibrationBin = {
  lower: number;
  upper: number;
  matches: number;
  predicted: number;
  observed: number;
};

export type ModelReport = Scores & {
  key: ModelKey;
  label: string;
  calibration: CalibrationBin[];
};

export type Difference = {
  metric: MetricKey;
  mean: number;
  lower: number;
  upper: number;
  significant: boolean;
};

export type Comparison = {
  reference: Exclude<ModelKey, "model">;
  metrics: Difference[];
};

export type YearResult = {
  year: number;
  matches: number;
  elo: Scores;
  model: Scores;
};

export type Segment = {
  dimension: "surface" | "tourney_level" | "best_of" | "experience";
  title: string;
  value: string;
  label: string;
  matches: number;
} & Record<ModelKey, Scores>;

export type Performance = {
  models: ModelReport[];
  comparisons: Comparison[];
  yearly: YearResult[];
  segments: Segment[];
};

export type Period = {
  name: "train" | "validation" | "test";
  label: string;
  start: string;
  end: string;
  matches: number;
};

export type Overview = {
  source: {
    repository: string;
    revision: string;
    snapshot: boolean;
    upstream: "available" | "missing" | "unreachable";
    upstreamRepository: string;
    reason: string;
  };
  dataset: {
    totalMatches: number;
    completedMatches: number;
    retirements: number;
    walkovers: number;
    unknownScores: number;
    discardedRows: number;
    players: number;
    firstDate: string;
    lastDate: string;
  };
  periods: Period[];
};

export type FeatureShare = { name: string; family: string; label: string; share: number };
export type FamilyShare = { key: string; label: string; share: number };

export type ModelDetails = {
  elo: {
    initialRating: number;
    kNumerator: number;
    kOffset: number;
    kShape: number;
    surfaceWeight: number;
  };
  gradientBoosting: {
    library: string;
    hyperparameters: Record<string, number>;
    trees: number;
    trials: number;
    searchSpace: Record<string, number[]>;
    validationLogLoss: number;
    calibration: { chosen: string; candidates: Record<string, number> };
  };
  walkForward: {
    tuningYear: number;
    hyperparameters: Record<string, number>;
    firstYear: number;
    lastYear: number;
  };
  importance: { features: FeatureShare[]; families: FamilyShare[] };
};

export type ReplaySummary = {
  slug: string;
  title: string;
  date: string;
  surface: string;
  players: [string, string];
  shortNames: [string, string];
  winner: 0 | 1;
  score: string;
  points: number;
  preMatch: { model: number; elo: number };
  outOfSample: boolean;
};

export type Opportunity =
  | "break_point_0"
  | "break_point_1"
  | "set_point_0"
  | "set_point_1"
  | "match_point_0"
  | "match_point_1";

export type ReplayPoint = {
  n: number;
  server: 0 | 1;
  winner: 0 | 1;
  p: number;
  sets: [number, number];
  games: [number, number];
  points: [string, string];
  tiebreak: boolean;
  opportunities: Opportunity[];
  outcome: "break" | "set" | "match" | null;
};

export type Moment = {
  n: number;
  kind: "low" | "saved" | "set" | "swing";
  text: string;
};

export type Replay = ReplaySummary & {
  format: { bestOf: number; finalSet: string };
  sets: [number, number][];
  tiebreaks: ([number, number] | null)[];
  serveWin: [number, number];
  tourServeWin: number;
  firstServer: 0 | 1;
  timeline: ReplayPoint[];
  moments: Moment[];
};
