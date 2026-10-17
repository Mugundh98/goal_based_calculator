import { expect, test } from '@playwright/test'

import { addGoal, signUp } from './helpers'

const year = String(new Date().getFullYear() + 10)

test('create, edit and delete a goal', async ({ page }) => {
  await signUp(page)
  await addGoal(page, { name: 'College fund', type: 'Education', cost: '2000000', year, sip: '10000' })

  const card = page.locator('div.rounded-lg', { has: page.getByRole('heading', { name: 'College fund' }) })
  await expect(card).toBeVisible()
  await expect(card.getByText(`${year} (in 10 years)`)).toBeVisible()
  await expect(card.getByText('SIP needed')).toBeVisible()
  // ₹20 lakh at 6% inflation for 10 years is about ₹35.8 lakh.
  await expect(card.getByText(/of ₹35\.8\d L/)).toBeVisible()

  await card.getByRole('button', { name: 'Edit' }).click()
  const dialog = page.getByRole('dialog')
  await dialog.getByLabel('Name').fill('Engineering degree')
  await dialog.getByRole('button', { name: 'Save changes' }).click()
  await expect(page.getByRole('heading', { name: 'Engineering degree' })).toBeVisible()

  page.once('dialog', (confirm) => confirm.accept())
  await page.getByRole('button', { name: 'Delete' }).click()
  await expect(page.getByText('No goals yet')).toBeVisible()
})

test('the goal form explains invalid input before saving', async ({ page }) => {
  await signUp(page)
  await page.goto('/goals')
  await page.getByRole('button', { name: 'Add goal' }).first().click()
  const dialog = page.getByRole('dialog')
  await dialog.getByLabel('Target year').fill(String(new Date().getFullYear()))
  await dialog.getByRole('button', { name: 'Add goal' }).click()
  await expect(dialog.getByText('Choose a goal type')).toBeVisible()
  await expect(dialog.getByText('Give the goal a name')).toBeVisible()
  await expect(dialog.getByText('Must be after this year')).toBeVisible()
})
