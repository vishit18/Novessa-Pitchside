import { defineConfig, devices } from '@playwright/test'

/**
 * End-to-end smoke tests: `npm run e2e`.
 *
 * Starts both servers itself, so nothing needs to be running first:
 * - the gateway from the repo root: `uv run uvicorn backend.app.main:app --port 8000`, with
 *   PRELOAD=1 so the three demo matches are built before the first test connects
 * - the Vite dev server for the frontend
 * Locally, servers that are already up are reused.
 */
export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? 'github' : 'list',
  use: {
    baseURL: 'http://127.0.0.1:5173',
    viewport: { width: 1920, height: 1080 },
    trace: 'retain-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'], viewport: { width: 1920, height: 1080 } },
    },
  ],
  webServer: [
    {
      command: 'uv run uvicorn backend.app.main:app --host 127.0.0.1 --port 8000',
      cwd: '..',
      env: { PRELOAD: '1' },
      // Ready means the showcase match is built, not just that the process answers. The first
      // request for a match builds its timeline (a few seconds of CPU); asking here keeps that
      // cost out of the first test, where parallel workers would all wait on it at once.
      url: 'http://127.0.0.1:8000/matches/derby_01/state?t=1',
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
    {
      command: 'npm run dev -- --host 127.0.0.1 --port 5173 --strictPort',
      url: 'http://127.0.0.1:5173',
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
  ],
})
