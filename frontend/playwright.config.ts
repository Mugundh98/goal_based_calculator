import { defineConfig, devices } from '@playwright/test'

const CI = Boolean(process.env.CI)

/**
 * End-to-end tests: a real browser drives the real frontend, API and database.
 * Locally they reuse the dev servers if they are running; otherwise (and in CI) Playwright
 * starts both. Each test signs up its own new user, so tests never share data.
 */
export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  expect: { timeout: 10_000 },
  retries: CI ? 1 : 0,
  workers: 1, // one database: run the flows one after another
  reporter: CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://127.0.0.1:5173',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      command: 'uv run uvicorn app.main:app --host 127.0.0.1 --port 8000',
      cwd: '../backend',
      url: 'http://127.0.0.1:8000/api/health',
      reuseExistingServer: !CI,
      timeout: 120_000,
    },
    {
      command: 'npm run dev',
      url: 'http://127.0.0.1:5173',
      reuseExistingServer: !CI,
      timeout: 120_000,
    },
  ],
})
