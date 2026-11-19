import assert from 'node:assert/strict';
import test from 'node:test';
import { monthSeed, weeklyPeriod } from '../common.mjs';
import { selectFrame } from '../frame.mjs';

test('weekly UTC IDs share Monday until next week, including year rollover', () => {
  for (const [instant, period] of [
    ['2026-11-16T00:00:00Z', '2026-11-16'], ['2026-11-18T23:30:00Z', '2026-11-16'],
    ['2026-11-22T23:59:59Z', '2026-11-16'], ['2026-11-23T00:00:00Z', '2026-11-23'],
    ['2027-01-01T01:00:00Z', '2026-12-28'], ['2027-01-04T00:00:00Z', '2027-01-04'],
    ['2026-11-22T18:30:00-08:00', '2026-11-23'],
  ]) assert.equal(weeklyPeriod(new Date(instant)), period);
});

test('weekly seeds are distinct while historical monthly seeds remain stable', () => {
  assert.equal(monthSeed('2026-11'), 202611);
  assert.equal(monthSeed('2026-11-16'), 20261116);
  assert.equal(monthSeed('2026-11-23'), 20261123);
  assert.notEqual(monthSeed('2026-11-16'), monthSeed('2026-11-23'));
});

test('release identifiers reject malformed, non-Monday and impossible dates', () => {
  for (const period of ['2026-13', '2026-00', '2026-11-18', '2026-02-30', '2026-11-31',
    '2026-11-16/other', '2026-11-pilot', '0000-01', '2026-1', null]) {
    assert.throws(() => monthSeed(period), Error);
  }
});

test('weekly frame generation is reproducible, distinct and respects prior reservations', () => {
  const csv = Array.from({ length: 100000 }, (_, i) => `${i + 1},site${i + 1}.example`).join('\n');
  const initial = new Set(['site1.example']);
  const a = selectFrame(csv, initial, 100, monthSeed('2026-11-16'));
  assert.deepEqual(a, selectFrame(csv, initial, 100, monthSeed('2026-11-16')));
  const excluded = new Set([...initial, ...a.map(site => site.domain)]);
  const b = selectFrame(csv, excluded, 100, monthSeed('2026-11-23'));
  assert.equal(b.length, 100);
  assert.ok(b.every(site => !excluded.has(site.domain)));
  assert.notDeepEqual(a, b);
});
