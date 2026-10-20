import { expect, test } from '@playwright/test'

/**
 * derby_01 (ASH v KES) is the showcase match. Times below come from its overlay export
 * (GET /matches/derby_01/overlays.jsonl): Tobias Wragg (ASH-17) scores a penalty at show_at
 * 1607.6 s, and Tunde Balogun (ASH-16) is sent off for a second yellow at 4493.4 s.
 * If the demo seeds change, update these from the export.
 */
const PENALTY_GOAL_T = 1602
const RED_CARD_T = 4488

test('broadcast view shows the pitch, the score and the goal overlay', async ({ page }) => {
  await page.goto(`/watch?match=derby_01&t=${PENALTY_GOAL_T}&speed=1`)

  // The pitch canvas is up and the score bug has data.
  await expect(page.locator('canvas')).toBeVisible()
  await expect(page.getByLabel('Match clock')).toHaveText(/^26:\d\d$/, { timeout: 20_000 })

  // The goal card arrives over the socket and wipes in as a lower third.
  const lowerThird = page.locator('[aria-live="polite"]')
  await expect(lowerThird).toContainText('Goal', { timeout: 20_000 })
  await expect(lowerThird).toContainText('Tobias Wragg')
  await expect(page.getByLabel('ASH score')).toHaveText('1')
})

test('split view shows the same goal to both viewers', async ({ page }) => {
  await page.goto(`/split?match=derby_01&t=${PENALTY_GOAL_T}&speed=1`)
  const cards = page.locator('[aria-live="polite"]')
  await expect(cards).toHaveCount(2)
  await expect(cards.nth(0)).toContainText('Goal', { timeout: 20_000 })
  await expect(cards.nth(1)).toContainText('Goal', { timeout: 5_000 })
})

test('player focus follows one player and shows their live stats', async ({ page }) => {
  await page.goto(`/watch?match=derby_01&t=${PENALTY_GOAL_T}&speed=1&player=ASH-17`)
  const card = page.getByRole('region', { name: /Tobias Wragg/ })
  await expect(card.getByRole('heading', { name: 'Tobias Wragg' })).toBeVisible()
  // Live speed comes from the frame stream; distance from player_stats. Both replace the dash.
  await expect(card.getByText(/^\d+\.\d\s*km\/h$/).first()).toBeVisible({ timeout: 20_000 })
  await expect(card.getByText(/^\d+\.\d\d\s*km$/)).toBeVisible({ timeout: 20_000 })
})

test('following a player who is sent off shows it on the card', async ({ page }) => {
  await page.goto(`/watch?match=derby_01&t=${RED_CARD_T}&speed=1&player=ASH-16`)
  await expect(page.locator('[aria-live="polite"]')).toContainText('Red card', { timeout: 20_000 })
  const card = page.getByRole('region', { name: /Tunde Balogun/ })
  await expect(card.getByRole('status')).toHaveText('Sent off', { timeout: 20_000 })
})
