import { expect, test } from '@playwright/test'

/**
 * The Control Room needs only the gateway. In CI there is no model endpoint, so the agents are
 * off and the screen says so; with one configured, the same plates show live counters.
 */
test('control room lists the five airing agents and the gateway state', async ({ page }) => {
  await page.goto('/control?match=derby_01')

  await expect(page.getByRole('heading', { name: 'Control room', level: 1 })).toBeVisible()
  for (const name of ['Producer', 'Analyst', 'Verifier', 'Narrator', 'Safety gate']) {
    await expect(page.getByRole('article', { name: new RegExp(`^${name}:`) })).toBeVisible()
  }

  // Either the agents are off (CI) or the start button is live. Never a blank panel.
  const off = page.getByText('The agents are switched off on this gateway')
  const start = page.getByRole('button', { name: /Start the agents|Agents (running|finished)/ })
  await expect(off.or(start)).toBeVisible({ timeout: 20_000 })
})
