import { spawnSync } from 'node:child_process';
import { copyFileSync, existsSync, readdirSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { fileURLToPath } from 'node:url';

const project = process.argv[2];
const scenarios = { 'insecure-login': ['fail', 'insecure'], 'secure-login': ['pass', 'secure'] };
if (!Object.hasOwn(scenarios, project)) throw new Error('Select insecure-login or secure-login.');
const [directory, name] = scenarios[project];
const root = fileURLToPath(new URL('../../', import.meta.url));
const artifacts = join(root, 'artifacts/browser-demo');
const destination = join(artifacts, `${name}.webm`);
const output = join(artifacts, directory);
rmSync(destination, { force: true }); // A failed browser launch must not leave a stale named video.
rmSync(output, { recursive: true, force: true });

// Run the actual Playwright CLI, with its output and failure stack intact.
const result = spawnSync(process.execPath, [
  fileURLToPath(import.meta.resolve('@playwright/test/cli')), 'test',
  '--config', 'examples/browser-demo/playwright.config.js', `--project=${project}`,
], { cwd: root, stdio: 'inherit' });
if (result.error) throw result.error;
if (result.signal) {
  process.kill(process.pid, result.signal);
} else {
  // Playwright finishes and closes its context before we copy the real recording.
  const videos = existsSync(output) ? readdirSync(output, { recursive: true }).filter(path => path.endsWith('.webm')) : [];
  if (videos.length === 1) {
    copyFileSync(join(output, videos[0]), destination);
    console.log(`\nBrowser recording: artifacts/browser-demo/${name}.webm`);
  } else {
    console.error(`Browser recording unavailable (found ${videos.length} videos). See Playwright output above.`);
  }
  console.log(`Exit code: ${result.status}`);
  // Forward the child's actual status, including the genuine failed assertion.
  process.exitCode = result.status;
}
