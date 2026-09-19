import type { ModelRunner } from "./predict";

let pending: Promise<ModelRunner> | null = null;

async function createRunner(modelUrl: string): Promise<ModelRunner> {
  const ort = await import("onnxruntime-web/wasm");
  ort.env.wasm.numThreads = 1;
  const session = await ort.InferenceSession.create(modelUrl, { executionProviders: ["wasm"] });
  return async (rows, rowCount, columnCount) => {
    const output = await session.run(
      { features: new ort.Tensor("float64", rows, [rowCount, columnCount]) },
      ["probabilities"],
    );
    const probabilities = output.probabilities;
    if (!probabilities) {
      throw new Error("Sortie du modèle absente");
    }
    return probabilities.data as Float32Array;
  };
}

export function loadRunner(modelUrl: string): Promise<ModelRunner> {
  if (!pending) {
    pending = createRunner(modelUrl);
    pending.catch(() => {
      pending = null;
    });
  }
  return pending;
}
