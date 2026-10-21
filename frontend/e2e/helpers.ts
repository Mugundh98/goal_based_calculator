import { expect, type Page } from '@playwright/test'

// A throwaway test password for accounts created only in the local or CI test database.
export const PASSWORD = 'e2e-Test-1234'

/** Sign up a brand-new user through the UI and land on the dashboard. */
export async function signUp(page: Page, name = 'Priya Tester'): Promise<string> {
  const email = `e2e-${Date.now()}-${Math.floor(Math.random() * 1e6)}@example.com`
  await page.goto('/register')
  await page.getByLabel('Full name').fill(name)
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Password', { exact: true }).fill(PASSWORD)
  await page.getByLabel('Confirm password').fill(PASSWORD)
  await page.getByLabel('Security question').selectOption({ label: 'In which city were you born?' })
  await page.getByLabel('Answer').fill('Visakhapatnam')
  await page.getByRole('button', { name: 'Create account' }).click()
  await expect(page).toHaveURL(/\/dashboard$/)
  await expect(page.getByRole('heading', { name: `Welcome, ${name.split(' ')[0]}` })).toBeVisible()
  return email
}

/** Fill the goal dialog and save it. */
export async function addGoal(page: Page, goal: { name: string; type: string; cost: string; year: string; sip: string }) {
  await page.goto('/goals')
  await page.getByRole('button', { name: 'Add goal' }).first().click()
  const dialog = page.getByRole('dialog')
  await dialog.getByLabel('Type').selectOption({ label: goal.type })
  await dialog.getByLabel('Name').fill(goal.name)
  await dialog.getByLabel("Cost in today's money").fill(goal.cost)
  await dialog.getByLabel('Target year').fill(goal.year)
  await dialog.getByLabel('Monthly SIP').fill(goal.sip)
  await dialog.getByRole('button', { name: 'Add goal' }).click()
  await expect(dialog).toBeHidden()
}
