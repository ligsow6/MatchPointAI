import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import {
  buildSearchIndex,
  decodePlayers,
  headToHeadBetween,
  reliabilityIssues,
  searchPlayers,
} from "./players";
import type { HeadToHeadPayload, PlayerRecord, PlayersPayload } from "./types";

const dataDir = path.resolve(__dirname, "../../public/data");
const payload = JSON.parse(
  readFileSync(path.join(dataDir, "players.json"), "utf-8"),
) as PlayersPayload;
const pairs = JSON.parse(
  readFileSync(path.join(dataDir, "h2h.json"), "utf-8"),
) as HeadToHeadPayload;
const players = decodePlayers(payload);
const thresholds = {
  reliableMatches: payload.reliableMatches,
  inactiveDays: payload.inactiveDays,
  dataThrough: payload.dataThrough,
};

function byName(name: string): PlayerRecord {
  const player = players.find((item) => item.name === name);
  if (!player) {
    throw new Error(`${name} absent de players.json`);
  }
  return player;
}

describe("players.json", () => {
  it("décode chaque joueur avec toutes les colonnes", () => {
    expect(players.length).toBeGreaterThan(1000);
    for (const player of players.slice(0, 50)) {
      expect(player.played).toBeGreaterThanOrEqual(payload.minMatches);
      expect(Number.isFinite(player.elo)).toBe(true);
    }
  });

  it("signale un joueur inactif depuis plus d'un an (cas réel)", () => {
    const issues = reliabilityIssues(byName("Roger Federer"), thresholds);
    expect(issues.some((issue) => issue.startsWith("aucun match depuis"))).toBe(true);
  });

  it("signale un historique insuffisant (cas réel)", () => {
    const newcomer = players.find((player) => player.played < payload.reliableMatches);
    expect(newcomer).toBeDefined();
    const issues = reliabilityIssues(newcomer as PlayerRecord, thresholds);
    expect(issues.some((issue) => issue.startsWith("seulement"))).toBe(true);
  });

  it("ne signale rien pour un joueur actif et expérimenté", () => {
    const active = [...players]
      .filter((player) => player.lastMatch >= payload.dataThrough.slice(0, 4))
      .sort((left, right) => right.elo - left.elo)[0];
    expect(reliabilityIssues(active as PlayerRecord, thresholds)).toEqual([]);
  });

  it("oriente le face-à-face selon le joueur A", () => {
    const nadal = byName("Rafael Nadal");
    const federer = byName("Roger Federer");
    const [nadalWins, federerWins] = headToHeadBetween(pairs, nadal.id, federer.id);
    expect(nadalWins + federerWins).toBeGreaterThan(20);
    expect(headToHeadBetween(pairs, federer.id, nadal.id)).toEqual([federerWins, nadalWins]);
  });

  it("gère deux joueurs qui ne se sont jamais affrontés", () => {
    expect(headToHeadBetween(pairs, byName("Rafael Nadal").id, 1)).toEqual([0, 0]);
  });

  it("trouve un joueur sans accents ni majuscules", () => {
    const index = buildSearchIndex(players);
    expect(searchPlayers(index, "federer")[0]?.name).toBe("Roger Federer");
    expect(searchPlayers(index, "fed")[0]?.name).toBe("Roger Federer");
    expect(searchPlayers(index, "rafa")[0]?.name).toBe("Rafael Nadal");
    expect(searchPlayers(index, "nov djok")[0]?.name).toBe("Novak Djokovic");
    expect(searchPlayers(index, "")).toEqual([]);
  });
});
