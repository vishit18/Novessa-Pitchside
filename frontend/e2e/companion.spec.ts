import { expect, test } from '@playwright/test'

/**
 * derby_01: the first goal airs at about 367 s (see broadcast.spec.ts). The Companion lists
 * cards as the viewer's own clock reaches them, and "What did I miss?" must stop at that clock.
 */
test.use({ viewport: { width: 390, height: 844 }, hasTouch: true })

test('companion feed fills as the match reaches a goal, and catch-up stays spoiler-safe', async ({
  page,
}) => {
  await page.goto('/companion?match=derby_01&t=340&speed=4')

  await expect(page.getByRole('heading', { name: 'The match so far' })).toBeVisible()
  const goal = page.getByRole('heading', { name: /Goal/ }).first()
  await expect(goal).toBeVisible({ timeout: 30_000 })

  // The "why" panel opens and names where the card came from.
  await page.getByRole('button', { name: 'Why am I seeing this?' }).first().click()
  await expect(page.getByText(/match numbers|match data/).first()).toBeVisible()

  // Catch-up covers the match up to the viewer's clock and says so.
  await page.getByRole('button', { name: 'What did I miss?' }).click()
  const sheet = page.getByRole('dialog')
  await expect(sheet.getByRole('heading', { name: /^Caught up to \d\d:\d\d$/ })).toBeVisible()
  await expect(sheet).toContainText('and nothing after it')
  await expect(sheet).toContainText('Ashford Rovers lead Kestrel Bay FC 1-0')
  // Not yet reached at this point of the match: the first red card is near 57'.
  await expect(sheet).not.toContainText('Red card')
})

test('the catch-up sheet works from the keyboard and asks the gateway once', async ({ page }) => {
  const catchupCalls: string[] = []
  page.on('request', (r) => r.url().includes('/catchup') && catchupCalls.push(r.url()))
  await page.goto('/companion?match=derby_01&t=340&speed=4')
  await expect(page.getByRole('heading', { name: /Goal/ }).first()).toBeVisible({ timeout: 30_000 })

  // Closed, the sheet is out of the accessibility tree and the tab order.
  await expect(page.getByRole('dialog')).toHaveCount(0)

  const trigger = page.getByRole('button', { name: 'What did I miss?' })
  await trigger.focus()
  await page.keyboard.press('Enter')
  const sheet = page.getByRole('dialog')
  await expect(sheet).toBeVisible()
  // Focus moves into the sheet, and the match clock ticking underneath does not refetch it.
  await expect(sheet.getByRole('button', { name: 'Back to the match' })).toBeFocused()
  await page.waitForTimeout(2500)
  expect(catchupCalls).toHaveLength(1)

  // Escape closes it and hands focus back to the button that opened it.
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog')).toHaveCount(0)
  await expect(trigger).toBeFocused()
})
