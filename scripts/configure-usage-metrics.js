// Bundle a public, write-only PostHog project token before publishing packages.
// Sets the destination for default-enabled audit reporting; explicit opt-outs win.
import { writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const ROOT = fileURLToPath(new URL('../', import.meta.url));

export async function configureUsageMetrics({ token, region = 'us', root = ROOT }) {
  if (typeof token !== 'string' || token !== token.trim() || !/^phc_[A-Za-z0-9_-]{20,200}$/.test(token)) {
    throw new Error('Set COOKIEGUARD_POSTHOG_PROJECT_TOKEN to a public phc_ project token. Personal API keys are not accepted.');
  }
  if (region !== 'us' && region !== 'eu') {
    throw new Error('COOKIEGUARD_POSTHOG_REGION must be us or eu.');
  }
  // Validation above permits only characters safe in both language literals.
  await writeFile(join(root, 'packages/core/src/usage-config.js'),
    '// Public PostHog ingestion configuration. Audit usage reporting defaults on; explicit opt-outs win.\n' +
    `export const PROJECT_TOKEN = '${token}';\nexport const REGION = '${region}';\n`);
  await writeFile(join(root, 'integrations/python/src/cookieguard/_usage_config.py'),
    '"""Public PostHog ingestion configuration. Audit reporting defaults on; explicit opt-outs win."""\n' +
    `PROJECT_TOKEN = "${token}"\nREGION = "${region}"\n`);
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try {
    await configureUsageMetrics({
      token: process.env.COOKIEGUARD_POSTHOG_PROJECT_TOKEN,
      region: process.env.COOKIEGUARD_POSTHOG_REGION ?? 'us',
    });
    process.stdout.write('Configured the public PostHog project for Node.js and Python. Audit reporting defaults on; explicit opt-outs win.\n');
  } catch {
    process.stderr.write('Usage configuration failed. Supply a public phc_ project token and a us/eu region, and check that both package source directories are writable.\n');
    process.exitCode = 1;
  }
}
