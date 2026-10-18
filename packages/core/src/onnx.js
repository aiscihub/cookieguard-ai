import { readFile } from 'node:fs/promises';
import { AuditError, classes } from './safety.js';
import { cleanTriage, extractCookieFeatures, FEATURE_NAMES } from './normalize.js';

export async function createOnnxClassifier({ modelPath, metadataPath }) {
  let runtime;
  let session;
  let meta;
  try {
    // The Node runtime reads this before native initialization. Never restore it:
    // later sessions in this process must also remain telemetry-free.
    process.env.ORT_DISABLE_TELEMETRY = '1';
    runtime = await import('onnxruntime-node');
    meta = JSON.parse(await readFile(metadataPath, 'utf8'));
    if (JSON.stringify(meta.feature_names) !== JSON.stringify(FEATURE_NAMES)
      || JSON.stringify([...meta.classes].sort()) !== JSON.stringify([...classes].sort())) throw new Error();
    // Buffer loading also keeps local filenames out of native error diagnostics.
    const model = await readFile(modelPath);
    session = await runtime.InferenceSession.create(model, { executionProviders: ['cpu'], logSeverityLevel: 4 });
  } catch { throw new AuditError('MODEL'); }
  return {
    mode: 'onnx',
    async classify(cookie) {
      try {
        const features = extractCookieFeatures(cookie);
        const vector = new Float32Array(FEATURE_NAMES.map(name => features[name] || 0));
        const result = await session.run({ features: new runtime.Tensor('float32', vector, [1, FEATURE_NAMES.length]) });
        const label = String(result.label.data[0]);
        const probabilities = result.probabilities.data;
        const index = meta.classes.indexOf(label);
        if (index < 0 || probabilities.length !== meta.classes.length) throw new Error();
        return cleanTriage({ mode: 'onnx', label, score: probabilities[index] });
      } catch { throw new AuditError('MODEL'); }
    },
    async dispose() { try { await session.release(); } catch { throw new AuditError('MODEL'); } },
  };
}
