import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: '.', testMatch: '**/login.demo.js', workers: 1, retries: 0,
  timeout: 30000, reporter: 'list',
  use: { browserName: 'chromium', serviceWorkers: 'block', trace: 'off', screenshot: 'off', video: 'off' },
  projects: [
    { name: 'insecure-login', outputDir: '../../artifacts/ci-demo/fail' },
    { name: 'secure-login', outputDir: '../../artifacts/ci-demo/pass' },
  ],
});
