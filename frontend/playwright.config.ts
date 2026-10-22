import { defineConfig, devices } from '@playwright/test'

/**
 * End-to-end smoke tests: `npm run e2e`.
 *
 * Starts both servers itself, so nothing needs to be running first:
 * - the gateway from the repo root: `uv run uvicorn backend.app.main:app --port 8000`, with
 *   PRELOAD=1 so the three demo matches are built before the first test connects
 * - the Vite dev server for the frontend
 * Locally, servers that are already up are reused. E2E_GATEWAY_PORT and E2E_WEB_PORT move both
 * off 8000 and 5173 when something else on the machine already holds those ports.
 */
const GATEWAY_PORT = process.env.E2E_GATEWAY_PORT ?? '8000'
const WEB_PORT = process.env.E2E_WEB_PORT ?? '5173'

export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? 'github' : 'list',
  use: {
    baseURL: `http://127.0.0.1:${WEB_PORT}`,
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
      command: `uv run uvicorn backend.app.main:app --host 127.0.0.1 --port ${GATEWAY_PORT}`,
      cwd: '..',
      env: {
        PRELOAD: '1',
        CORS_ORIGINS: `http://127.0.0.1:${WEB_PORT},http://localhost:${WEB_PORT}`,
      },
      // Ready means the showcase match is built, not just that the process answers. The first
      // request for a match builds its timeline (a few seconds of CPU); asking here keeps that
      // cost out of the first test, where parallel workers would all wait on it at once.
      url: `http://127.0.0.1:${GATEWAY_PORT}/matches/derby_01/state?t=1`,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
    },
    {
      command: `npm run dev -- --host 127.0.0.1 --port ${WEB_PORT} --strictPort`,
      env: { VITE_GATEWAY_URL: `ws://127.0.0.1:${GATEWAY_PORT}` },
      url: `http://127.0.0.1:${WEB_PORT}`,
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
  ],
})
