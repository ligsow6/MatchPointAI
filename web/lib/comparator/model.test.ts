import { readFileSync } from "node:fs";
import path from "node:path";
import * as ort from "onnxruntime-web";
import { describe, expect, it } from "vitest";
import { featureNames } from "../features";
import { contextFor, decodePlayers, headToHeadBetween } from "./players";
import { predictMatch, type ModelRunner } from "./predict";
import type { HeadToHeadPayload, ModelMetadata, PlayersPayload } from "./types";

const root = path.resolve(__dirname, "../../public");
const metadata = JSON.parse(
  readFileSync(path.join(root, "model", "metadata.json"), "utf-8"),
) as ModelMetadata;
const payload = JSON.parse(
  readFileSync(path.join(root, "data", "players.json"), "utf-8"),
) as PlayersPayload;
const pairs = JSON.parse(
  readFileSync(path.join(root, "data", "h2h.json"), "utf-8"),
) as HeadToHeadPayload;
const players = new Map(decodePlayers(payload).map((player) => [player.id, player]));

async function nodeRunner(): Promise<ModelRunner> {
  ort.env.wasm.numThreads = 1;
  const session = await ort.InferenceSession.create(
    readFileSync(path.join(root, "model", metadata.file)),
  );
  return async (rows, rowCount, columnCount) => {
    const output = await session.run(
      { features: new ort.Tensor("float64", rows, [rowCount, columnCount]) },
      ["probabilities"],
    );
    return output.probabilities?.data as Float32Array;
  };
}

describe("modèle ONNX exécuté par onnxruntime-web", () => {
  it("attend exactement les variables calculées en TypeScript", () => {
    expect(metadata.features).toEqual(featureNames());
  });

  it("retrouve les probabilités Python à 1e-6 près", async () => {
    const runner = await nodeRunner();
    expect(metadata.sanity.length).toBeGreaterThanOrEqual(3);
    for (const sanity of metadata.sanity) {
      const playerA = players.get(sanity.playerA);
      const playerB = players.get(sanity.playerB);
      const preset = metadata.presets.find((item) => item.key === sanity.preset);
      if (!playerA || !playerB || !preset) {
        throw new Error("cas de contrôle incomplet");
      }
      const probability = await predictMatch(
        runner,
        metadata,
        playerA,
        playerB,
        contextFor(preset, sanity.surface, metadata.neutralRestDays),
        headToHeadBetween(pairs, playerA.id, playerB.id),
      );
      expect(Math.abs(probability - sanity.probability)).toBeLessThanOrEqual(1e-6);
    }
  });
});
