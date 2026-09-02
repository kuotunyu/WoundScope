import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { defineConfig } from '@playwright/test';

const modulePath = fileURLToPath(import.meta.url);
const moduleDirectory = path.dirname(modulePath);
const reportRoot = process.env.WOUNDSCOPE_PAGES_REPORT_DIR;

if (!reportRoot) {
  throw new Error('REPORT_DIR_MISSING');
}

export default defineConfig({
  testDir: moduleDirectory,
  testMatch: 'pages.spec.mjs',
  fullyParallel: false,
  outputDir: path.join(reportRoot, 'playwright-results'),
  projects: [
    { name: 'chromium', use: { browserName: 'chromium' } },
    { name: 'firefox', use: { browserName: 'firefox' } },
    { name: 'webkit', use: { browserName: 'webkit' } },
  ],
  reporter: [['list']],
  retries: 0,
  use: {
    baseURL: 'http://127.0.0.1:4173',
    screenshot: 'off',
    trace: 'off',
    video: 'off',
  },
  webServer: {
    command: `"${process.execPath}" "${path.join(moduleDirectory, 'test-server.mjs')}"`,
    cwd: moduleDirectory,
    env: { ...process.env },
    reuseExistingServer: false,
    timeout: 30_000,
    url: 'http://127.0.0.1:4173/WoundScope/',
  },
  workers: 1,
});
