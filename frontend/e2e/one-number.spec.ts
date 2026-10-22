import { expect, test } from '@playwright/test'

/**
 * One-number mode: the viewer picks a single measure in onboarding and the broadcast shows that
 * number, always, instead of the full set of overlays.
 */
test('one-number mode shows the running leader for the chosen measure', async ({ page }) => {
  await page.goto('/start?match=derby_01')
  await page.getByRole('button', { name: /Ashford Rovers.*Kestrel Bay/ }).click()
  await page.getByRole('button', { name: /Just one number/ }).click()
  await page.getByRole('button', { name: /Sprint speed/ }).click()
  await page.getByRole('button', { name: /No side/ }).click()
  await page.getByRole('button', { name: /English/ }).click()
  await expect(page).toHaveURL(/\/watch/)

  // The chip says what this viewer asked for, and the number is on screen.
  await page.goto('/watch?match=derby_01&t=600&speed=1')
  await expect(page.getByRole('button', { name: /Watching as/ })).toContainText('Sprint speed')
  const readout = page.getByRole('group', { name: 'Fastest sprint' })
  await expect(readout).toContainText(/\d+\.\d\s*km\/h/, { timeout: 20_000 })
})

test('picking a normal persona clears one-number mode', async ({ page }) => {
  await page.goto('/start?match=derby_01')
  await page.getByRole('button', { name: /Ashford Rovers.*Kestrel Bay/ }).click()
  await page.getByRole('button', { name: /Just one number/ }).click()
  await page.getByRole('button', { name: /Shot speed/ }).click()
  await page.getByRole('button', { name: 'Back' }).click()
  await page.getByRole('button', { name: 'Back' }).click()
  await page.getByRole('button', { name: /Casual/ }).click()
  await page.getByRole('button', { name: /No side/ }).click()
  await page.getByRole('button', { name: /English/ }).click()
  await page.goto('/watch?match=derby_01&t=600&speed=1')
  await expect(page.getByRole('button', { name: /Watching as/ })).toContainText('Casual')
  await expect(page.getByRole('group', { name: 'Hardest shot' })).toHaveCount(0)
})
