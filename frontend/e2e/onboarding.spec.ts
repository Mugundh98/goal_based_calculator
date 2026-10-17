import { expect, test } from '@playwright/test'

import { signUp } from './helpers'

test('a new user signs up, completes the profile and gets a risk profile', async ({ page }) => {
  await signUp(page)

  // Step 1: financial profile
  await page.getByRole('link', { name: 'Start' }).first().click()
  await expect(page).toHaveURL(/\/profile$/)
  await page.getByLabel('Date of birth').fill('1990-05-17')
  await page.getByLabel('Employment').selectOption({ label: 'Salaried' })
  await page.getByLabel('Dependants').fill('2')
  await page.getByLabel('Take-home income').fill('150000')
  await page.getByLabel('Household expenses').fill('60000')
  await page.getByLabel('Loan EMIs').fill('10000')
  await page.getByLabel('Cash savings').fill('400000')
  await page.getByLabel('Existing investments').fill('200000')
  await page.getByRole('button', { name: 'Save and continue' }).click()

  // Step 2: the seven-question risk questionnaire (the middle answer each time)
  await expect(page).toHaveURL(/\/risk\/questionnaire$/)
  for (let question = 0; question < 7; question++) {
    await page.getByRole('radio').nth(2).check()
    const next = page.getByRole('button', { name: question < 6 ? 'Next' : 'See my risk profile' })
    await next.click()
  }
  await expect(page).toHaveURL(/\/risk$/)
  await expect(page.getByText(/Conservative|Moderate|Aggressive/).first()).toBeVisible()
  await expect(page.getByText('/ 100').first()).toBeVisible()

  // The dashboard now shows both steps as done.
  await page.getByRole('link', { name: 'Dashboard' }).click()
  await expect(page.getByRole('heading', { name: 'Financial profile (done)' })).toBeAttached()
  await expect(page.getByRole('heading', { name: 'Risk profile (done)' })).toBeAttached()
})
