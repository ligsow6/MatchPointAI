import type {
  HeadToHead,
  HeadToHeadPayload,
  MatchContext,
  PlayerRecord,
  PlayersPayload,
  Preset,
  Surface,
} from "./types";

export function decodePlayers(payload: PlayersPayload): PlayerRecord[] {
  return payload.players.map((row) => {
    const entry: Record<string, unknown> = {};
    payload.columns.forEach((column, index) => {
      entry[column] = row[index] ?? null;
    });
    return entry as PlayerRecord;
  });
}

export function headToHeadBetween(
  payload: HeadToHeadPayload,
  playerA: number,
  playerB: number,
): HeadToHead {
  const [first, second] = playerA < playerB ? [playerA, playerB] : [playerB, playerA];
  const entry = payload.pairs[String(first)]?.find(([opponent]) => opponent === second);
  const wins: HeadToHead = entry ? [entry[1], entry[2]] : [0, 0];
  return playerA === first ? wins : [wins[1], wins[0]];
}

export function contextFor(
  preset: Preset,
  surface: Surface,
  neutralRestDays: number,
): MatchContext {
  return {
    surface,
    level: preset.level,
    roundOrder: preset.roundOrder,
    bestOf: preset.bestOf,
    drawSize: preset.drawSize,
    restDays: neutralRestDays,
    tourneyMatches: 0,
  };
}

export function eloProbability(
  playerA: PlayerRecord,
  playerB: PlayerRecord,
  surface: Surface,
): number {
  const surfaceKey = `elo${surface}` as const;
  const difference =
    0.5 * (playerA.elo - playerB.elo) + 0.5 * (playerA[surfaceKey] - playerB[surfaceKey]);
  return 1 / (1 + Math.pow(10, -difference / 400));
}

export type ReliabilityThresholds = {
  reliableMatches: number;
  inactiveDays: number;
  dataThrough: string;
};

const DAY = 24 * 60 * 60 * 1000;

export function daysSinceLastMatch(player: PlayerRecord, dataThrough: string): number {
  return Math.round(
    (Date.parse(`${dataThrough}T00:00:00Z`) - Date.parse(`${player.lastMatch}T00:00:00Z`)) / DAY,
  );
}

export function reliabilityIssues(
  player: PlayerRecord,
  thresholds: ReliabilityThresholds,
): string[] {
  const issues: string[] = [];
  if (player.played < thresholds.reliableMatches) {
    issues.push(`seulement ${player.played} matchs dans la base`);
  }
  if (daysSinceLastMatch(player, thresholds.dataThrough) > thresholds.inactiveDays) {
    issues.push(
      `aucun match depuis le ${new Intl.DateTimeFormat("fr-FR", { dateStyle: "long", timeZone: "UTC" }).format(new Date(`${player.lastMatch}T00:00:00Z`))}`,
    );
  }
  return issues;
}

export function normalize(text: string): string {
  return text
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9 ]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

export type SearchIndex = { player: PlayerRecord; key: string; tokens: string[] }[];

export function buildSearchIndex(players: PlayerRecord[]): SearchIndex {
  return players.map((player) => {
    const key = normalize(player.name);
    return { player, key, tokens: key.split(" ") };
  });
}

export function searchPlayers(index: SearchIndex, query: string, limit = 8): PlayerRecord[] {
  const needle = normalize(query);
  if (!needle) {
    return [];
  }
  const parts = needle.split(" ");
  return index
    .filter((entry) => parts.every((part) => entry.tokens.some((token) => token.startsWith(part))))
    .map((entry) => ({
      player: entry.player,
      rank:
        entry.key.startsWith(needle) || entry.tokens.some((token) => token.startsWith(needle))
          ? 0
          : 1,
    }))
    .sort(
      (left, right) =>
        left.rank - right.rank ||
        right.player.played - left.player.played ||
        right.player.elo - left.player.elo,
    )
    .slice(0, limit)
    .map((item) => item.player);
}
