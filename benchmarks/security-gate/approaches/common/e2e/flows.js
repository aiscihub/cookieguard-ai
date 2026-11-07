// The developer's existing login steps, shared unchanged by every approach.
import { expect } from '@playwright/test';
import { DEMO_USER } from '../app.js';

export async function signIn(page) {
  await page.goto('/login');
  await page.getByLabel('Username').fill(DEMO_USER.username);
  await page.getByLabel('Password').fill(DEMO_USER.password);
  await page.getByRole('button', { name: 'Sign in' }).click();
  await expect(page).toHaveURL(/\/notes$/);
  // The notes list loads through the API after the page obtains its API token.
  await expect(page.locator('#notes li').first()).toHaveText('Welcome to Acme Notes');
}

export async function signOut(page) {
  await page.getByRole('button', { name: 'Sign out' }).click();
  await expect(page).toHaveURL(/\/login$/);
}
