import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createOnnxClassifier } from '@cookieguard/core/onnx';
import { normalizeCookie, evaluateCookiePolicy, exitCode, formatJson } from '@cookieguard/core';

test('real ONNX inference is explicitly labeled, never confirms identity, disables runtime telemetry', async () => {
  const classifier = await createOnnxClassifier({ modelPath: 'extension-standalone/model/cookieguard_model.onnx', metadataPath: 'extension-standalone/model/model_meta.json' });
  try {
    const input = { name: 'session_id', value: 'SENTINEL_MODEL_TOKEN_8ef910ab', secure: false, httpOnly: false };
    const triage = await classifier.classify(input);
    assert.equal(triage.mode, 'onnx');
    assert.equal(triage.origin, 'extension-onnx-uncalibrated');
    assert.equal(process.env.ORT_DISABLE_TELEMETRY, '1');
    const report = evaluateCookiePolicy([normalizeCookie(input, { triage })]);
    assert.equal(exitCode(report), 0);
    assert.equal(report.summary.confirmedViolations, 0);
    assert.equal(formatJson(report).includes(input.value), false, 'Sensitive sentinel was emitted');
  } finally { await classifier.dispose(); }
});

test('model failures use a fixed error and never silently fall back', async () => {
  await assert.rejects(createOnnxClassifier({ modelPath: 'SENTINEL_MODEL_PATH', metadataPath: 'SENTINEL_MODEL_PATH' }), error => {
    assert.equal(error.code, 'MODEL');
    assert.equal(error.message.includes('SENTINEL_MODEL_PATH'), false); return true;
  });
});
