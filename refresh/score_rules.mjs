import { createRequire } from 'node:module';
import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { args, die, ROOT, writeJSON } from './common.mjs';
try {
  const a = args({ rows: { type: 'string' }, out: { type: 'string' } });
  const engine = createRequire(import.meta.url)(resolve(ROOT, 'packages/core/vendor/engine.cjs'));
  const rows = readFileSync(a.rows, 'utf8').split('\n').filter(Boolean).map(JSON.parse);
  writeJSON(a.out, rows.map(row => {
    const features = Object.fromEntries(engine.FEATURE_NAMES.map((name, i) => [name, row.features[i]]));
    return Number(engine.classifyRuleBased(features).type === 'tracking');
  }));
} catch { die(); }
