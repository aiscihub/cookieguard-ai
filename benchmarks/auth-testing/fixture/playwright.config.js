import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: 'e2e',
  use: { baseURL: 'http://127.0.0.1:3000' },
  webServer: {
    command: 'node server.js',
    url: 'http://127.0.0.1:3000/health',
    reuseExistingServer: !process.env.CI,
  },
});
