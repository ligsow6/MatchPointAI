import type { HeadToHead, MatchContext, PlayerRecord, Surface } from "./comparator/types";

const SURFACE_CATEGORIES = ["Hard", "Clay", "Grass"] as const;
const LEVEL_CATEGORIES = ["G", "M", "A", "F", "D", "O"] as const;

const DIFFERENCE_FEATURES = [
  "elo",
  "surface_elo",
  "form_short",
  "form_long",
  "surface_form_short",
  "surface_form_long",
  "rest_days",
  "serve_won",
  "return_won",
  "age",
  "height",
] as const;

const SIDE_FEATURES = [
  "elo",
  "surface_elo",
  "elo_played",
  "surface_played",
  "rank",
  "rank_points",
  "age",
  "form_short",
  "surface_form_short",
  "rest_days",
  "tourney_matches",
  "serve_won",
  "return_won",
  "left_handed",
  "h2h_wins",
] as const;

type SideName =
  | (typeof DIFFERENCE_FEATURES)[number]
  | (typeof SIDE_FEATURES)[number]
  | "form_long"
  | "surface_form_long";

type SideValues = Record<SideName, number>;

const SURFACE_COLUMNS = SURFACE_CATEGORIES.map((surface) => [
  surface,
  `surface_${surface.toLowerCase()}`,
]);
const LEVEL_COLUMNS = LEVEL_CATEGORIES.map((level) => [level, `level_${level.toLowerCase()}`]);

export function featureNames(): string[] {
  const derived = ["elo_blend_diff", "log_rank_ratio", "log_points_ratio", "h2h_share"];
  const differences = DIFFERENCE_FEATURES.map((name) => `${name}_diff`);
  const sides = SIDE_FEATURES.flatMap((name) => [`${name}_a`, `${name}_b`]);
  const context = [
    ...SURFACE_COLUMNS.map(([, column]) => column as string),
    ...LEVEL_COLUMNS.map(([, column]) => column as string),
    "round_order",
    "best_of",
    "draw_size",
  ];
  return [...derived, ...differences, ...sides, ...context];
}

function missing(value: number | null): number {
  return value === null ? Number.NaN : value;
}

function surfaceElo(player: PlayerRecord, surface: Surface): number {
  return { Hard: player.eloHard, Clay: player.eloClay, Grass: player.eloGrass }[surface];
}

function surfacePlayed(player: PlayerRecord, surface: Surface): number {
  return { Hard: player.playedHard, Clay: player.playedClay, Grass: player.playedGrass }[surface];
}

function surfaceForm(player: PlayerRecord, surface: Surface): [number | null, number | null] {
  return {
    Hard: [player.formShortHard, player.formLongHard] as [number | null, number | null],
    Clay: [player.formShortClay, player.formLongClay] as [number | null, number | null],
    Grass: [player.formShortGrass, player.formLongGrass] as [number | null, number | null],
  }[surface];
}

function sideValues(
  player: PlayerRecord,
  context: MatchContext,
  headToHeadWins: number,
): SideValues {
  const [surfaceShort, surfaceLong] = surfaceForm(player, context.surface);
  return {
    elo: player.elo,
    surface_elo: surfaceElo(player, context.surface),
    elo_played: player.played,
    surface_played: surfacePlayed(player, context.surface),
    rank: missing(player.rank),
    rank_points: missing(player.rankPoints),
    age: missing(player.age),
    height: missing(player.height),
    left_handed: player.hand === "L" ? 1 : 0,
    form_short: missing(player.formShort),
    form_long: missing(player.formLong),
    surface_form_short: missing(surfaceShort),
    surface_form_long: missing(surfaceLong),
    rest_days: context.restDays,
    tourney_matches: context.tourneyMatches,
    serve_won: missing(player.serveWon),
    return_won: missing(player.returnWon),
    h2h_wins: headToHeadWins,
  };
}

export function buildFeatures(
  playerA: PlayerRecord,
  playerB: PlayerRecord,
  context: MatchContext,
  headToHead: HeadToHead,
): Record<string, number> {
  const a = sideValues(playerA, context, headToHead[0]);
  const b = sideValues(playerB, context, headToHead[1]);
  const features: Record<string, number> = {
    elo_blend_diff: 0.5 * (a.elo - b.elo) + 0.5 * (a.surface_elo - b.surface_elo),
    log_rank_ratio: Math.log(b.rank) - Math.log(a.rank),
    log_points_ratio: Math.log1p(a.rank_points) - Math.log1p(b.rank_points),
    h2h_share: (a.h2h_wins + 1.0) / (a.h2h_wins + b.h2h_wins + 2.0),
  };
  for (const name of DIFFERENCE_FEATURES) {
    features[`${name}_diff`] = a[name] - b[name];
  }
  for (const name of SIDE_FEATURES) {
    features[`${name}_a`] = a[name];
    features[`${name}_b`] = b[name];
  }
  for (const [surface, column] of SURFACE_COLUMNS) {
    features[column as string] = context.surface === surface ? 1 : 0;
  }
  for (const [level, column] of LEVEL_COLUMNS) {
    features[column as string] = context.level === level ? 1 : 0;
  }
  features.round_order = context.roundOrder;
  features.best_of = context.bestOf;
  features.draw_size = context.drawSize;
  return features;
}

export function featureVector(
  features: Record<string, number>,
  names: readonly string[],
): Float64Array {
  return Float64Array.from(names, (name) => {
    const value = features[name];
    if (value === undefined) {
      throw new Error(`Variable absente : ${name}`);
    }
    return value;
  });
}
