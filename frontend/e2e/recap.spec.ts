import { expect, test } from '@playwright/test'

/**
 * Works with the agents on (a written recap) and off (CI: the page falls back to the computed
 * numbers and key moments). Either way the page must show its title, the key moments and let
 * the viewer switch half, language and persona through the address bar.
 */
test('recap page loads, shows key moments and switches language and half', async ({ page }) => {
  await page.goto('/recap?match=derby_01&kind=half_time&persona=casual&lang=en')

  await expect(page.getByRole('heading', { name: 'Half-time recap', level: 1 })).toBeVisible()
  await expect(page.getByRole('heading', { name: 'Key moments' })).toBeVisible({ timeout: 60_000 })
  // The first goal falls inside the first half, so it is in the timeline.
  await expect(page.getByText('Tobias Wragg scored for Ashford Rovers').first()).toBeVisible()

  await page.getByRole('button', { name: 'Español' }).click()
  await expect(page).toHaveURL(/lang=es/)

  await page.getByRole('button', { name: 'Full-time' }).click()
  await expect(page).toHaveURL(/kind=full_time/)
  await expect(page.getByRole('heading', { name: 'Full-time recap', level: 1 })).toBeVisible()
})
