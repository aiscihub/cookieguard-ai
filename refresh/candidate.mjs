// Test-only adapter. This file is never imported by a shipped package.
import './common.mjs';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { normalizeName, readJSON, sha } from './common.mjs';
import { extractCookieFeatures, FEATURE_NAMES } from '../packages/core/src/index.js';

export async function createCandidate(directory) {
  const meta = readJSON(resolve(directory, 'meta.json'));
  const model = readFileSync(resolve(directory, 'model.onnx'));
  const lookupBytes = readFileSync(resolve(directory, 'lookup.json'));
  if (sha(model) !== meta.onnxSha256 || sha(lookupBytes) !== meta.lookupSha256 ||
      JSON.stringify(meta.featureNames) !== JSON.stringify(FEATURE_NAMES)) throw new Error('candidate-integrity');
  const lookup = JSON.parse(lookupBytes);
  const tables = [new Map(lookup.raw.map(row => [row.name, row])),
    new Map(lookup.normalized.map(row => [row.name, row])), new Map(lookup.ocdExact.map(row => [row.name, row]))];
  const prefixes = [...lookup.ocdPrefix].sort((a, b) => b.name.length - a.name.length || a.name.localeCompare(b.name));
  const ort = await import('onnxruntime-node');
  const session = await ort.InferenceSession.create(model, { executionProviders: ['cpu'], logSeverityLevel: 4,
    intraOpNumThreads: 1, interOpNumThreads: 1 });
  let calls = 0;
  return {
    mode: 'onnx',
    get calls() { return calls; },
    async classify(cookie) {
      calls++;
      const hit = tables[0].get(cookie.name) || tables[1].get(normalizeName(cookie.name)) ||
        tables[2].get(cookie.name) || prefixes.find(row => cookie.name.startsWith(row.name));
      const features = extractCookieFeatures(cookie);
      // Execute the forest even on lookup hits during canaries to prove the model is loaded.
      const result = await session.run({ features: new ort.Tensor('float32',
        Float32Array.from(FEATURE_NAMES.map(name => features[name] || 0)), [1, FEATURE_NAMES.length]) });
      const prob = Number(result.probabilities.data[1]);
      const tracker = hit ? hit.label === 1 : prob >= meta.threshold;
      return { mode: 'onnx', label: tracker ? 'tracking' : 'other', score: hit ? 1 : tracker ? prob : 1 - prob };
    },
    async dispose() { await session.release(); }
  };
}
