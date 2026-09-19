import { buildFeatures, featureVector } from "../features";
import { applyCalibration } from "./calibration";
import type { HeadToHead, MatchContext, ModelMetadata, PlayerRecord } from "./types";

export type ModelRunner = (
  rows: Float64Array,
  rowCount: number,
  columnCount: number,
) => Promise<ArrayLike<number>>;

export async function predictMatch(
  runner: ModelRunner,
  metadata: ModelMetadata,
  playerA: PlayerRecord,
  playerB: PlayerRecord,
  context: MatchContext,
  headToHead: HeadToHead,
): Promise<number> {
  const names = metadata.features;
  const forward = featureVector(buildFeatures(playerA, playerB, context, headToHead), names);
  const backward = featureVector(
    buildFeatures(playerB, playerA, context, [headToHead[1], headToHead[0]]),
    names,
  );
  const rows = new Float64Array(names.length * 2);
  rows.set(forward, 0);
  rows.set(backward, names.length);
  const probabilities = await runner(rows, 2, names.length);
  const forwardWin = probabilities[1] ?? Number.NaN;
  const backwardWin = probabilities[3] ?? Number.NaN;
  return applyCalibration(0.5 * (forwardWin + 1 - backwardWin), metadata.calibration);
}
