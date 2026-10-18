import { defineConfig } from '@playwright/test';
import ciDemo from '../ci-demo/playwright.config.js';

export default defineConfig(ciDemo, {
  testDir: '../ci-demo',
  use: {
    browserDemo: true, headless: false,
    viewport: { width: 1280, height: 720 },
    video: { mode: 'on', size: { width: 1280, height: 720 } },
  },
  projects: [
    { name: 'insecure-login', outputDir: '../../artifacts/browser-demo/fail' },
    { name: 'secure-login', outputDir: '../../artifacts/browser-demo/pass' },
  ],
});
