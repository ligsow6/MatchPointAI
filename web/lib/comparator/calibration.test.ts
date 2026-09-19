import { describe, expect, it } from "vitest";
import { applyCalibration, interpolate } from "./calibration";

describe("calibration", () => {
  it("interpole comme numpy.interp, bornes comprises", () => {
    const xs = [0.1, 0.5, 0.9];
    const ys = [0.2, 0.4, 1.0];
    expect(interpolate(0, xs, ys)).toBe(0.2);
    expect(interpolate(1, xs, ys)).toBe(1.0);
    expect(interpolate(0.5, xs, ys)).toBe(0.4);
    expect(interpolate(0.7, xs, ys)).toBeCloseTo(0.7, 12);
  });

  it("laisse la probabilité intacte sans calibration", () => {
    expect(applyCalibration(0.63, { kind: "aucune" })).toBe(0.63);
  });

  it("applique la formule de Platt", () => {
    const value = applyCalibration(0.7, { kind: "platt", coefficient: 0.8, intercept: 0.1 });
    const expected = 1 / (1 + Math.exp(-(0.8 * Math.log(0.7 / 0.3) + 0.1)));
    expect(value).toBeCloseTo(expected, 12);
  });

  it("symétrise la calibration isotonique", () => {
    const calibration = { kind: "isotonique" as const, x: [0, 0.4, 1], y: [0, 0.3, 1] };
    const direct = applyCalibration(0.8, calibration);
    const mirrored = applyCalibration(0.2, calibration);
    expect(direct + mirrored).toBeCloseTo(1, 12);
  });
});
