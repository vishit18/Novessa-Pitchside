import { expect, test } from '@playwright/test'

/**
 * The first goal of derby_01 is at 40:17 (t_match 2417.9). Start just before it so the
 * test sees a real overlay arrive from the gateway and render.
 */
const GOAL_URL = '/watch?match=derby_01&t=2414&speed=1'

test('broadcast view shows the pitch, the score and the goal overlay', async ({ page }) => {
  await page.goto(GOAL_URL)

  // The pitch canvas is up and the score bug has data.
  await expect(page.locator('canvas')).toBeVisible()
  await expect(page.getByLabel('Match clock')).toHaveText(/^40:\d\d$/, { timeout: 20_000 })

  // The goal card arrives over the socket and wipes in as a lower third.
  const lowerThird = page.locator('[aria-live="polite"]')
  await expect(lowerThird).toContainText('Goal', { timeout: 20_000 })
  await expect(lowerThird).toContainText('Ishaan Sodhi')
  await expect(page.getByLabel('KES score')).toHaveText('1')
})

test('split view shows the same goal to both viewers', async ({ page }) => {
  await page.goto('/split?match=derby_01&t=2414&speed=1')
  const cards = page.locator('[aria-live="polite"]')
  await expect(cards).toHaveCount(2)
  await expect(cards.nth(0)).toContainText('Goal', { timeout: 20_000 })
  await expect(cards.nth(1)).toContainText('Goal', { timeout: 5_000 })
})
