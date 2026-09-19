import type { Calibration } from "./types";

const PROBABILITY_FLOOR = 1e-6;

function clip(probability: number): number {
  return Math.min(Math.max(probability, PROBABILITY_FLOOR), 1 - PROBABILITY_FLOOR);
}

function logit(probability: number): number {
  const bounded = clip(probability);
  return Math.log(bounded / (1 - bounded));
}

export function interpolate(value: number, xs: readonly number[], ys: readonly number[]): number {
  const last = xs.length - 1;
  const firstX = xs[0];
  const lastX = xs[last];
  const firstY = ys[0];
  const lastY = ys[last];
  if (firstX === undefined || lastX === undefined || firstY === undefined || lastY === undefined) {
    return value;
  }
  if (value <= firstX) {
    return firstY;
  }
  if (value >= lastX) {
    return lastY;
  }
  let low = 0;
  let high = last;
  while (high - low > 1) {
    const middle = (low + high) >> 1;
    if ((xs[middle] ?? 0) <= value) {
      low = middle;
    } else {
      high = middle;
    }
  }
  const x0 = xs[low] ?? 0;
  const x1 = xs[high] ?? 0;
  const y0 = ys[low] ?? 0;
  const y1 = ys[high] ?? 0;
  return x1 === x0 ? y1 : y0 + ((value - x0) * (y1 - y0)) / (x1 - x0);
}

export function applyCalibration(probability: number, calibration: Calibration): number {
  switch (calibration.kind) {
    case "platt":
      return (
        1 / (1 + Math.exp(-(calibration.coefficient * logit(probability) + calibration.intercept)))
      );
    case "isotonique": {
      const direct = interpolate(probability, calibration.x, calibration.y);
      const mirrored = interpolate(1 - probability, calibration.x, calibration.y);
      return 0.5 * (direct + 1 - mirrored);
    }
    default:
      return probability;
  }
}
