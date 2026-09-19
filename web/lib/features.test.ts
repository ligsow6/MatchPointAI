import { readFileSync } from "node:fs";
import path from "node:path";
import { describe, expect, it } from "vitest";
import type { HeadToHead, MatchContext, PlayerRecord } from "./comparator/types";
import { buildFeatures, featureNames, featureVector } from "./features";

type FixtureCase = {
  name: string;
  playerA: PlayerRecord;
  playerB: PlayerRecord;
  context: MatchContext;
  headToHead: [number, number];
  expected: Record<string, number | null>;
};

const fixture = JSON.parse(
  readFileSync(path.resolve(__dirname, "../../fixtures/comparator_features.json"), "utf-8"),
) as { cases: FixtureCase[] };

describe("variables du comparateur (fixture partagée avec Python)", () => {
  it("couvre plusieurs cas", () => {
    expect(fixture.cases.length).toBeGreaterThanOrEqual(3);
  });

  it.each(fixture.cases.map((item) => [item.name, item] as const))("%s", (_, item) => {
    const headToHead: HeadToHead = [item.headToHead[0], item.headToHead[1]];
    const computed = buildFeatures(item.playerA, item.playerB, item.context, headToHead);
    expect(Object.keys(item.expected)).toEqual(featureNames());
    expect(Object.keys(computed).sort()).toEqual([...featureNames()].sort());
    for (const [name, value] of Object.entries(item.expected)) {
      const observed = computed[name];
      if (value === null) {
        expect(Number.isNaN(observed), name).toBe(true);
      } else {
        expect(Math.abs((observed ?? Number.NaN) - value), name).toBeLessThanOrEqual(
          1e-12 * Math.max(1, Math.abs(value)),
        );
      }
    }
  });

  it("ordonne le vecteur selon la liste fournie et refuse une variable inconnue", () => {
    const item = fixture.cases[0];
    if (!item) {
      throw new Error("fixture vide");
    }
    const features = buildFeatures(item.playerA, item.playerB, item.context, [1, 2]);
    const vector = featureVector(features, ["h2h_wins_b", "h2h_wins_a"]);
    expect(Array.from(vector)).toEqual([2, 1]);
    expect(() => featureVector(features, ["inconnue"])).toThrow("inconnue");
  });
});
