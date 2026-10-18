export const SENTINELS = Object.freeze([
  'COOKIEGUARD_DEMO_SENTINEL_4e29bc7f',
  'SENTINEL_SESSION_NEVER_SERIALIZE_84af20',
  'SENTINEL_MODEL_TOKEN_8ef910ab',
  'SENTINEL_MODEL_PATH',
  'BENCHMARK_SENTINEL_NOT_A_REAL_SESSION_13ac98',
]);

export function assertNoSentinels(contents) {
  const buffer = Buffer.isBuffer(contents) ? contents : Buffer.from(String(contents));
  if (SENTINELS.some(value => buffer.includes(Buffer.from(value)))) {
    // Never include the offending output, filename, or token in this error.
    throw new Error('Sensitive sentinel detected. Output withheld; release gate failed.');
  }
}
