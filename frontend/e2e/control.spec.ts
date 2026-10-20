import { expect, test } from '@playwright/test'

/**
 * The Control Room needs only the gateway. In CI there is no model endpoint, so the agents are
 * off; with one configured, the same plates show live counters.
 */
test('control room lists the five airing agents and the gateway state', async ({ page }) => {
  await page.goto('/control?match=derby_01')

  await expect(page.getByRole('heading', { name: 'Control room', level: 1 })).toBeVisible()
  for (const name of ['Producer', 'Analyst', 'Verifier', 'Narrator', 'Safety gate']) {
    await expect(page.getByRole('article', { name: new RegExp(`^${name}:`) })).toBeVisible()
  }

  // The start control is on screen and the gateway answered (no offline banner). With agents
  // off the button is disabled and the page says why; with a model endpoint it is live.
  await expect(
    page.getByRole('button', { name: /Start the agents|Agents (running|finished)/ }),
  ).toBeVisible()
  await expect(page.getByRole('alert')).toHaveCount(0, { timeout: 10_000 })
})
