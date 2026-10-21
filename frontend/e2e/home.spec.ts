import { expect, test } from '@playwright/test'

/** Feedback from the first full walk-through: a newcomer must know what this is, and get anywhere. */
test('home says what the product is and links to every page', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { level: 1 })).toContainText('same broadcast')
  // One goal told three ways, by persona and language.
  await expect(page.getByText('Analyst, English')).toBeVisible()
  await expect(page.getByText('First match, हिन्दी')).toBeVisible()
  const nav = page.getByRole('navigation', { name: 'Pages' })
  for (const name of [
    'Watch',
    'Side by side',
    'Phone view',
    'Recap',
    'Real footage',
    'Control room',
  ])
    await expect(nav.getByRole('link', { name })).toBeVisible()
  await nav.getByRole('link', { name: 'Real footage' }).click()
  await expect(page).toHaveURL(/\/real/)
})

test('first-time viewers go from home to the setup questions', async ({ page }) => {
  await page.goto('/')
  await page.evaluate(() => localStorage.clear())
  await page.getByRole('button', { name: 'Start watching' }).click()
  await expect(page).toHaveURL(/\/start/)
  await expect(page.getByRole('heading', { name: 'How do you watch?' })).toBeVisible()
})

test('the timeline seeks the broadcast', async ({ page }) => {
  await page.goto('/watch?match=derby_01&t=600&speed=1')
  const bug = page.getByLabel('Match clock')
  await expect(bug).toHaveText(/^1\d:\d\d$/, { timeout: 20_000 })
  await page.mouse.move(400, 400)
  await page.getByRole('button', { name: 'Forward 30 seconds' }).click()
  await page.getByRole('button', { name: 'Pause' }).click()
  const slider = page.getByRole('slider', { name: 'Match time' })
  await slider.focus()
  // Keyboard on the native range input: End jumps to the final whistle, then commit on key up.
  await page.keyboard.press('Home')
  await expect(bug).toHaveText(/^00:0\d$/, { timeout: 20_000 })
})

test('split view shows what each viewer has been told', async ({ page }) => {
  await page.goto('/split?match=derby_01&t=1590&speed=1')
  const v1 = page.getByRole('region', { name: 'Viewer 1' })
  const v2 = page.getByRole('region', { name: 'Viewer 2' })
  await expect(v1.getByRole('button', { name: /Viewing as Analyst, English/ })).toBeVisible()
  await expect(v2.getByRole('button', { name: /Viewing as First match, Español/ })).toBeVisible()
  // The goal at 26:47 reaches both records. (In each viewer's language when Translator is
  // configured; CI runs without it, so check the clock rather than the words.)
  for (const n of [1, 2])
    await expect(page.getByText(`What viewer ${n} has been told`).locator('..')).toContainText(
      '26:47',
      { timeout: 45_000 },
    )
})

test('ask the analyst opens from the keyboard and answers or says why not', async ({ page }) => {
  await page.goto('/watch?match=derby_01&t=2400&speed=1')
  await expect(page.getByLabel('Match clock')).toHaveText(/^4\d:\d\d$/, { timeout: 20_000 })
  await page.keyboard.press('/')
  const panel = page.getByRole('dialog', { name: 'Ask the analyst' })
  await expect(panel).toBeVisible()
  await expect(panel).toContainText(/Uses the match up to \d\d:\d\d, nothing after/)
  await panel.getByRole('button', { name: 'Who is on top right now, and why?' }).click()
  // CI runs with the agents off: the panel must say so, not hang or break.
  await expect(panel).toContainText(
    /Checked against the match data|Straight from the numbers|The analyst is off right now/,
    { timeout: 45_000 },
  )
  await page.keyboard.press('Escape')
  await expect(panel).toHaveCount(0)
})

test('a goal gets its own moment on screen', async ({ page }) => {
  await page.goto('/watch?match=derby_01&t=1600&speed=1')
  const sting = page.locator('[aria-live="assertive"]')
  await expect(sting).toContainText('Ashford Rovers', { timeout: 30_000 })
  await expect(sting).toContainText('Tobias Wragg')
})
