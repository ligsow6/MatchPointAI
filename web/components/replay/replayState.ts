import type { Replay, ReplayPoint } from "@/lib/types";
import { formatPercent } from "@/lib/format";

export type ScoreSnapshot = {
  index: number;
  probability: number;
  sets: [number, number];
  games: [number, number];
  points: [string, string];
  completedSets: [number, number][];
  nextServer: 0 | 1 | null;
  tiebreak: boolean;
  finished: boolean;
  point: ReplayPoint | null;
};

export const SPEEDS = [1, 2, 4, 8] as const;
export const POINTS_PER_SECOND_AT_1X = 6;

export function snapshotAt(replay: Replay, index: number): ScoreSnapshot {
  const point = index > 0 ? (replay.timeline[index - 1] ?? null) : null;
  const sets: [number, number] = point ? point.sets : [0, 0];
  const completed = sets[0] + sets[1];
  const finished = index >= replay.timeline.length;
  const upcoming = replay.timeline[index];
  return {
    index,
    probability: point ? point.p : replay.preMatch.model,
    sets,
    games: point ? point.games : [0, 0],
    points: point ? point.points : ["0", "0"],
    completedSets: replay.sets.slice(0, completed),
    nextServer: finished ? null : (upcoming?.server ?? replay.firstServer),
    tiebreak: point ? point.tiebreak : false,
    finished,
    point,
  };
}

export function scoreSentence(replay: Replay, snapshot: ScoreSnapshot): string {
  const [first, second] = replay.shortNames;
  if (snapshot.index === 0) {
    return `Avant le match. ${first} ${formatPercent(snapshot.probability)} de chances de victoire.`;
  }
  const setsText = `Sets ${snapshot.sets[0]}-${snapshot.sets[1]}`;
  const gamesText = snapshot.finished ? "" : `, jeux ${snapshot.games[0]}-${snapshot.games[1]}`;
  const pointsText =
    snapshot.finished || (snapshot.points[0] === "0" && snapshot.points[1] === "0")
      ? ""
      : `, ${snapshot.tiebreak ? "tie-break " : ""}${snapshot.points[0]}-${snapshot.points[1]}`;
  const leader = snapshot.probability >= 0.5 ? first : second;
  const leaderChance = Math.max(snapshot.probability, 1 - snapshot.probability);
  const ending = snapshot.finished
    ? `Victoire de ${replay.shortNames[replay.winner]}.`
    : `${leader} ${formatPercent(leaderChance)} de chances de victoire.`;
  return `Point ${snapshot.index} sur ${replay.timeline.length}. ${setsText}${gamesText}${pointsText}. ${ending}`;
}

export function eventAnnouncement(replay: Replay, point: ReplayPoint): string | null {
  const names = replay.shortNames;
  const loser = replay.winner === 0 ? 1 : 0;
  if (point.outcome === "match") {
    return `Balle de match convertie : ${names[point.winner]} remporte le match.`;
  }
  if (point.opportunities.includes(`match_point_${loser}`) && point.winner === replay.winner) {
    return `Balle de match sauvée par ${names[replay.winner]}.`;
  }
  if (point.outcome === "set") {
    return `${names[point.winner]} remporte le set. Sets ${point.sets[0]}-${point.sets[1]}.`;
  }
  if (point.outcome === "break") {
    return `Break de ${names[point.winner]}. Jeux ${point.games[0]}-${point.games[1]}.`;
  }
  return null;
}

export function setBoundaries(replay: Replay): { index: number; label: string }[] {
  return replay.timeline
    .map((point, position) => ({ point, index: position + 1 }))
    .filter(({ point }) => point.outcome === "set" || point.outcome === "match")
    .map(({ index }, setIndex) => ({ index, label: `Set ${setIndex + 1}` }));
}

export function gameRows(replay: Replay): { index: number; point: ReplayPoint }[] {
  return replay.timeline
    .map((point, position) => ({ point, index: position + 1 }))
    .filter(({ point, index }) => {
      const previous = replay.timeline[index - 2];
      if (!previous) {
        return false;
      }
      return (
        point.games[0] + point.games[1] !== previous.games[0] + previous.games[1] ||
        point.sets[0] + point.sets[1] !== previous.sets[0] + previous.sets[1]
      );
    });
}
