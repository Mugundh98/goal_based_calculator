import { readFileSync } from 'node:fs'

import { expect, test } from '@playwright/test'

import { addGoal, PASSWORD, signUp } from './helpers'

test('protected pages need a login and bring you back after it', async ({ page }) => {
  const email = await signUp(page)
  await page.getByRole('button', { name: 'Log out' }).click()

  await page.goto('/portfolio')
  await expect(page).toHaveURL(/\/login$/)
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Password').fill(PASSWORD)
  await page.getByRole('button', { name: 'Log in' }).click()
  await expect(page).toHaveURL(/\/portfolio$/)
  await expect(page.getByText('No investments recorded yet')).toBeVisible()
})

test('a normal user cannot open the admin dashboard', async ({ page }) => {
  await signUp(page)
  await expect(page.getByRole('link', { name: 'Admin' })).toHaveCount(0)
  await page.goto('/admin')
  await expect(page).toHaveURL(/\/dashboard$/)
  const status = await page.request.get('/api/admin/overview')
  expect(status.status()).toBe(401) // no token on a bare request: the API itself refuses
})

test('download my plan as a PDF', async ({ page }) => {
  await signUp(page, 'Report Tester')
  await addGoal(page, { name: 'House deposit', type: 'House', cost: '1500000', year: String(new Date().getFullYear() + 5), sip: '20000' })
  const [download] = await Promise.all([
    page.waitForEvent('download'),
    page.getByRole('button', { name: 'Download my plan (PDF)' }).click(),
  ])
  expect(download.suggestedFilename()).toMatch(/^goalwise-plan-\d{4}-\d{2}-\d{2}\.pdf$/)
  const pdf = readFileSync(await download.path())
  expect(pdf.subarray(0, 5).toString()).toBe('%PDF-')
  expect(pdf.length).toBeGreaterThan(2000)
})

test('the assistant page works with or without a Gemini key', async ({ page }) => {
  await signUp(page)
  await page.goto('/assistant')
  // In CI there is no key: the page must say so instead of failing.
  await expect(page.getByRole('heading', { name: /Ask the GoalWise assistant|The assistant is switched off/ })).toBeVisible()
})
