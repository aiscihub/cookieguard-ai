import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: '.', testMatch: '*.spec.js', fullyParallel: false, workers: 1, retries: 0,
  timeout: 30000, reporter: 'list',
  use: { baseURL: 'http://127.0.0.1:3000', serviceWorkers: 'block', trace: 'off', screenshot: 'off', video: 'off' },
  webServer: { command: 'node ../demo/server.js', url: 'http://127.0.0.1:3000', reuseExistingServer: false, timeout: 15000 },
});
