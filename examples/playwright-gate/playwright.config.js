import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: '.', testMatch: 'login.spec.js', outputDir: 'test-results', workers: 1, retries: 0, reporter: 'list',
  use: { baseURL: 'http://127.0.0.1:3100', trace: 'off', screenshot: 'off', video: 'off' },
  webServer: { command: 'node app.js', url: 'http://127.0.0.1:3100/login', reuseExistingServer: false,
    env: { FLAW: process.env.FLAW ?? '' } },
});
