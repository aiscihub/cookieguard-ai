import { chromium } from '@playwright/test';
import { createHash } from 'node:crypto';
import { spawnSync } from 'node:child_process';
import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { assertNoSentinels } from '../../scripts/lib/leakage.js';

const root = fileURLToPath(new URL('../../', import.meta.url));
const artifacts = join(root, 'artifacts/browser-demo');
const output = join(artifacts, 'final');
await mkdir(output, { recursive: true });

function command(binary, args) {
  const result = spawnSync(binary, args, { encoding: 'utf8', maxBuffer: 4 * 1024 * 1024 });
  assertNoSentinels(`${result.stdout ?? ''}${result.stderr ?? ''}`);
  if (result.error) throw result.error;
  if (result.status !== 0) throw new Error(`${binary} failed: ${result.stderr}`);
  return result.stdout;
}

function probe(path) {
  return JSON.parse(command('ffprobe', ['-v', 'error', '-count_frames', '-show_entries',
    'stream=codec_name,width,height,r_frame_rate,nb_read_frames:format=duration,size', '-of', 'json', path]));
}

const hash = data => createHash('sha256').update(data).digest('hex');
const escapeHtml = value => value.replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;').replaceAll('"', '&quot;');
const scenarios = [
  { name: 'insecure', mode: 'fail', exit: 1, number: '1', title: 'Login succeeds. CookieGuard finds missing HttpOnly.' },
  { name: 'secure', mode: 'pass', exit: 0, number: '2', title: 'Add HttpOnly. The same policy assertion passes.' },
];

// The displayed evidence is selected from real run logs. Missing evidence stops
// the export instead of substituting a demonstration verdict or terminal text.
for (const scenario of scenarios) {
  const log = await readFile(join(artifacts, `${scenario.mode}.log`), 'utf8');
  assertNoSentinels(log);
  const lines = log.split(/\r?\n/);
  function exactLine(pattern) {
    const matches = lines.filter(line => pattern.test(line));
    if (matches.length !== 1) throw new Error(`Missing or ambiguous evidence in ${scenario.mode}.log: ${pattern}`);
    return matches[0].trim();
  }
  scenario.excerpts = [
    exactLine(/^Running 1 test using 1 worker$/),
    exactLine(/^Login succeeded: /),
    exactLine(/^Authentication cookie observed: session_id \(confirmed identity\)\.$/),
    exactLine(scenario.exit ? /^CookieGuard: CG001 — Missing HttpOnly$/ : /^CookieGuard: policy passed$/),
    ...(scenario.exit ? [exactLine(/^\s+CookiePolicyError: CookieGuard confirmed cookie policy violations\.$/)] : []),
    exactLine(scenario.exit ? /^\s+1 failed\s*$/ : /^\s+1 passed \([\d.]+s\)\s*$/),
    exactLine(new RegExp(`^Exit code: ${scenario.exit}$`)),
  ];
  scenario.source = join(artifacts, `${scenario.name}.mp4`);
  const metadata = probe(scenario.source);
  if (Number(metadata.format.duration) < 7 || metadata.streams[0].width !== 1280 || metadata.streams[0].height !== 720) {
    throw new Error('Expected an existing 1280×720 browser demo recording at least 7 seconds long.');
  }
  scenario.provenance = {
    video: `artifacts/browser-demo/${scenario.name}.mp4`, videoSha256: hash(await readFile(scenario.source)),
    log: `artifacts/browser-demo/${scenario.mode}.log`, logSha256: hash(log),
    sourceDurationSeconds: Number(metadata.format.duration),
    sourceStartSeconds: 0, sourceEndSeconds: Math.min(11, Number(metadata.format.duration)), speed: 1,
    finalFrameHoldSeconds: Math.max(0, 11 - Number(metadata.format.duration)),
    excerpts: scenario.excerpts,
  };
}

const style = `
  * { box-sizing: border-box; }
  html, body { margin: 0; width: 1920px; height: 1080px; overflow: hidden; }
  body { background: #edf2f8; color: #14243a; font-family: Arial, sans-serif; }
  .brand { position: absolute; left: 48px; top: 38px; font-size: 29px; font-weight: 750; }
  .series { position: absolute; right: 48px; top: 47px; font-size: 18px; color: #536880; letter-spacing: 1.5px; }
  h1 { position: absolute; left: 48px; top: 103px; margin: 0; font-size: 49px; line-height: 1.2; letter-spacing: -1.3px; }
  .subtitle { position: absolute; left: 48px; top: 179px; margin: 0; font-size: 23px; color: #536880; }
  .browser-label { position: absolute; left: 48px; top: 238px; font-size: 18px; letter-spacing: 1px; }
  .browser { position: absolute; left: 42px; top: 268px; width: 1164px; height: 660px; background: white; border: 1px solid #d5dfeb; }
  .output { position: absolute; left: 1236px; top: 232px; width: 636px; height: 696px; background: #14243a; color: #edf3fc; border-radius: 12px; padding: 24px; }
  .output h2 { margin: 0 0 8px; font-size: 22px; font-weight: 600; }
  .source { margin: 0 0 24px; color: #b2c4df; font-size: 17px; }
  .line { font: 22px/1.38 Menlo, Consolas, monospace; white-space: pre-wrap; overflow-wrap: anywhere; margin: 0 0 17px; }
  .result { color: var(--accent); }
  .summary { font-size: 29px; font-weight: 700; margin-top: 19px; }
  .caption { position: absolute; left: 48px; top: 968px; font-size: 23px; font-weight: 600; }
  .provenance { position: absolute; left: 1236px; top: 955px; width: 636px; font-size: 17px; line-height: 1.5; color: #536880; }
  .closing { background: #14243a; color: #f5f8fc; text-align: center; }
  .closing .name { margin-top: 224px; font-size: 44px; font-weight: 700; color: #b9d0fa; }
  .closing .message { margin: 48px auto 64px; max-width: 1600px; font-size: 62px; line-height: 1.2; letter-spacing: -1px; font-weight: 700; }
  .closing .repository { display: inline-block; border-bottom: 3px solid #80aaff; padding-bottom: 18px; font-size: 59px; font-weight: 600; }
  .closing .details { margin-top: 58px; font-size: 25px; color: #b9c8dc; }
`;

function layout(scenario) {
  const excerpts = scenario.excerpts.map(line => {
    const summary = /^1 (failed|passed)/.test(line);
    const result = summary || /^(CookieGuard:|CookiePolicyError:|Exit code:)/.test(line);
    return `<p class="line${result ? ' result' : ''}${summary ? ' summary' : ''}">${escapeHtml(line)}</p>`;
  }).join('');
  return `<!doctype html><html><head><meta charset="utf-8"><style>${style}</style></head>
    <body style="--accent:${scenario.exit ? '#ffb6ba' : '#92e4bd'}">
      <div class="brand">CookieGuard CI</div><div class="series">PLAYWRIGHT / COOKIE SECURITY</div>
      <h1>${scenario.number} &nbsp; ${scenario.title}</h1>
      <p class="subtitle">Same login. Same security assertion. Only the HttpOnly attribute changes.</p>
      <div class="browser-label">CHROMIUM · ACTUAL BROWSER RECORDING</div><div class="browser"></div>
      <section class="output"><h2>Captured Playwright output</h2>
        <p class="source">${scenario.mode}.log · excerpts from this recorded run</p>${excerpts}</section>
      <div class="caption">npm run demo:browser:${scenario.mode}</div>
      <div class="provenance">Actual saved output alongside the browser replay.</div>
    </body></html>`;
}

const closing = `<!doctype html><html><head><meta charset="utf-8"><style>${style}</style></head>
  <body class="closing"><div class="name">CookieGuard CI</div>
    <div class="message">A successful login still needs secure cookies.</div>
    <div class="repository">github.com/aiscihub/cookieguard-ai</div>
    <div class="details">Open source · Local-first · Privacy-preserving</div>
  </body></html>`;

// Render only the editorial text/layout here. The browser footage is always
// taken directly from the original MP4 files, never reconstructed or simulated.
const browser = await chromium.launch({ headless: true });
try {
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  await page.route('**/*', route => route.abort());
  for (const [name, html] of [...scenarios.map(scenario => [scenario.name, layout(scenario)]), ['closing', closing]]) {
    assertNoSentinels(html);
    await writeFile(join(output, `${name}.html`), html);
    await page.setContent(html);
    await page.screenshot({ path: join(output, `${name}.png`) });
  }
} finally { await browser.close(); }

for (const scenario of scenarios) {
  command('ffmpeg', ['-hide_banner', '-loglevel', 'error', '-y',
    '-loop', '1', '-framerate', '25', '-i', join(output, `${scenario.name}.png`), '-i', scenario.source,
    '-filter_complex', '[1:v]setpts=PTS-STARTPTS,tpad=stop_mode=clone:stop_duration=11,trim=duration=11,scale=1152:648:flags=lanczos,setsar=1[clip];[0:v][clip]overlay=48:274:shortest=1,format=yuv420p[out]',
    '-map', '[out]', '-an', '-t', '11', '-r', '25', '-c:v', 'libx264', '-crf', '18', '-preset', 'medium',
    '-movflags', '+faststart', join(output, `${scenario.name}-segment.mp4`)]);
}
command('ffmpeg', ['-hide_banner', '-loglevel', 'error', '-y',
  '-loop', '1', '-framerate', '25', '-i', join(output, 'closing.png'), '-t', '3', '-an',
  '-c:v', 'libx264', '-crf', '18', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', join(output, 'closing-segment.mp4')]);
await writeFile(join(output, 'segments.txt'), "file 'insecure-segment.mp4'\nfile 'secure-segment.mp4'\nfile 'closing-segment.mp4'\n");
const final = join(artifacts, 'cookieguard-ci-demo-25s.mp4');
command('ffmpeg', ['-hide_banner', '-loglevel', 'error', '-y', '-f', 'concat', '-safe', '0',
  '-i', join(output, 'segments.txt'), '-c', 'copy', '-movflags', '+faststart', final]);
const metadata = probe(final);
if (Number(metadata.format.duration) !== 25 || metadata.streams[0].nb_read_frames !== '625') {
  throw new Error('The composed video must be exactly 25 seconds / 625 frames.');
}
const manifest = {
  output: 'artifacts/browser-demo/cookieguard-ci-demo-25s.mp4',
  sha256: hash(await readFile(final)), metadata,
  timeline: scenarios.map((scenario, index) => ({ startSeconds: index * 11, endSeconds: (index + 1) * 11, ...scenario.provenance }))
    .concat([{ startSeconds: 22, endSeconds: 25, text: 'github.com/aiscihub/cookieguard-ai' }]),
  presentation: 'Real browser recordings with verbatim excerpts of captured Playwright output. This is an edited composition, not a live desktop screen recording.',
};
await writeFile(join(output, 'manifest.json'), `${JSON.stringify(manifest, null, 2)}\n`);
console.log(`Created ${manifest.output} (25 seconds, 1920×1080, 25 fps).`);
