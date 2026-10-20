import { test, expect } from '@playwright/test';

const apiBaseUrl = 'http://localhost:8001/api/v1';

async function registerAndLogin(page, apiBaseUrl, email, password, fullName = 'Test User') {
  // Register via API
  await page.request.post(`${apiBaseUrl}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    data: { full_name: fullName, email, password },
  });
  // Login via API
  const loginResponse = await fetch(`${apiBaseUrl}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password })
  });
  const loginData = await loginResponse.json();
  // Set token in localStorage - navigate to app origin first
  await page.goto('/');
  await page.evaluate((token) => localStorage.setItem('devflow.access_token', token), loginData.access_token);
  return loginData.access_token;
}

test.describe('Journey C: Logout and Session Expiry', () => {
  test.beforeEach(async ({ page }) => {
    // Register and login with a unique test user
    const testEmail = `session-${Date.now()}-${Math.random().toString(36).substring(7)}@example.com`;
    const testPassword = 'password123';
    await registerAndLogin(page, apiBaseUrl, testEmail, testPassword, 'Session Test User');
    await page.goto('/');
    await expect(page).toHaveURL('/', { timeout: 10000 });
  });

  test('can log out and token is cleared', async ({ page }) => {
    await expect(page.locator('button:has-text("Log out")')).toBeVisible();

    await page.click('button:has-text("Log out")');
    await expect(page).toHaveURL(/.*login/, { timeout: 5000 });

    // Try to access protected page - should redirect to login
    await page.goto('/projects');
    await expect(page).toHaveURL(/.*login/, { timeout: 5000 });
  });

  test('protected pages redirect to login after logout', async ({ page }) => {
    await page.click('button:has-text("Log out")');
    await expect(page).toHaveURL(/.*login/);

    const protectedPaths = ['/projects', '/requirements', '/tasks', '/team', '/analytics', '/reports'];
    for (const path of protectedPaths) {
      await page.goto(path);
      await expect(page).toHaveURL(/.*login/, { timeout: 5000 });
    }
  });

  test('invalid/expired token triggers session expiry handler', async ({ page }) => {
    // Manually set an invalid token in localStorage
    await page.evaluate(() => {
      localStorage.setItem('devflow.access_token', 'invalid.token.here');
    });

    // Try to access protected resource - should trigger 401 and clear token
    await page.goto('/projects');
    await expect(page).toHaveURL(/.*login/, { timeout: 10000 });
  });

  test('public pages remain accessible after logout', async ({ page }) => {
    await page.click('button:has-text("Log out")');
    await expect(page).toHaveURL(/.*login/);

    // Registration page should still be accessible
    await page.goto('/register');
    await expect(page.locator('h1')).toContainText('Join your workspace');

    // Login page should still be accessible
    await page.goto('/login');
    await expect(page.locator('h1')).toContainText('Sign in to your workspace');
  });

  test('session persists across page reloads', async ({ page }) => {
    await page.reload();
    await expect(page).toHaveURL('/', { timeout: 5000 });
    // Dashboard page uses PageTitle component with role-specific title
    await expect(page.locator('h1, h2').first()).toBeVisible();

    // Navigate to projects and reload
    await page.goto('/projects');
    await expect(page.locator('h1:has-text("Projects")')).toBeVisible();
    await page.reload();
    await expect(page.locator('h1:has-text("Projects")')).toBeVisible();
  });
});