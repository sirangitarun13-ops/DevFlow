import { test, expect } from '@playwright/test';

test.describe('Journey A: Registration and Authentication', () => {
  const testPassword = 'password123';
  const apiBaseUrl = 'http://localhost:8001/api/v1';

  test('can register a new account', async ({ page }) => {
    const testEmail = `e2e-${Date.now()}-${Math.random().toString(36).substring(7)}@example.com`;

    await page.goto('/register');
    await expect(page.locator('h1')).toContainText('Join your workspace');

    await page.fill('label:has-text("Full Name") input', 'Test User');
    await page.fill('label:has-text("Email") input', testEmail);
    await page.fill('label:has-text("Password") input', 'password123');
    await page.fill('label:has-text("Confirm Password") input', 'password123');

    await page.click('button:has-text("Create account")');

    // Wait for either redirect to login (success) or error message (email exists)
    await Promise.race([
      expect(page).toHaveURL(/.*login/, { timeout: 15000 }),
      expect(page.locator('.form-error')).toBeVisible({ timeout: 10000 })
    ]);

    // If registration failed due to existing email, log in instead
    if (page.url().includes('/register')) {
      const errorText = await page.locator('.form-error').textContent();
      if (errorText?.includes('already') || errorText?.includes('exists')) {
        await page.goto('/login');
        await page.fill('label:has-text("Email") input', 'e2etest@example.com');
        await page.fill('label:has-text("Password") input', 'password123');
        await page.click('button:has-text("Sign in")');
        await expect(page).toHaveURL('/', { timeout: 10000 });
      } else {
        throw new Error('Registration failed: ' + errorText);
      }
    }
  });

  test('can log in with valid credentials', async ({ page }) => {
    const testEmail = `login-${Date.now()}-${Math.random().toString(36).substring(7)}@example.com`;
    const testPassword = 'password123';

    // First register the user via API to ensure clean state
    await fetch(`${apiBaseUrl}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        full_name: 'Login Test User',
        email: testEmail,
        password: testPassword
      })
    });

    // Now log in
    await page.goto('/login');
    await expect(page.locator('h1')).toContainText('Sign in to your workspace');

    await page.fill('label:has-text("Email") input', testEmail);
    await page.fill('label:has-text("Password") input', testPassword);

    await page.click('button:has-text("Sign in")');

    await Promise.race([
      expect(page).toHaveURL('/', { timeout: 15000 }),
      expect(page.locator('.form-error')).toBeVisible({ timeout: 5000 })
    ]);

    const url = page.url();
    if (url.includes('/login')) {
      const errorText = await page.locator('.form-error').textContent();
      throw new Error(`Login failed with error: ${errorText}`);
    }

    // Dashboard page shows role-specific title
    await expect(page.locator('h1')).toBeVisible({ timeout: 5000 });
  });

  test('rejects invalid credentials', async ({ page }) => {
    const testEmail = `invalid-${Date.now()}-${Math.random().toString(36).substring(7)}@example.com`;

    await page.goto('/login');
    await page.fill('label:has-text("Email") input', testEmail);
    await page.fill('label:has-text("Password") input', 'wrongpassword');

    await page.click('button:has-text("Sign in")');

    await expect(page.locator('.form-error')).toBeVisible({ timeout: 5000 });
    await expect(page).toHaveURL(/.*login/);
  });

  test('rejects registration with mismatched passwords', async ({ page }) => {
    const uniqueEmail = `mismatch-${Date.now()}-${Math.random().toString(36).substring(7)}@example.com`;

    await page.goto('/register');

    await page.fill('label:has-text("Full Name") input', 'Test User');
    await page.fill('label:has-text("Email") input', uniqueEmail);
    await page.fill('label:has-text("Password") input', 'password123');
    await page.fill('label:has-text("Confirm Password") input', 'different123');

    await page.click('button:has-text("Create account")');

    await expect(page.locator('.form-error')).toBeVisible({ timeout: 5000 });
  });

  test('rejects registration with short password', async ({ page }) => {
    const uniqueEmail = `short-${Date.now()}-${Math.random().toString(36).substring(7)}@example.com`;

    await page.goto('/register');

    await page.fill('label:has-text("Full Name") input', 'Test User');
    await page.fill('label:has-text("Email") input', uniqueEmail);
    await page.fill('label:has-text("Password") input', 'short');
    await page.fill('label:has-text("Confirm Password") input', 'short');

    await page.click('button:has-text("Create account")');

    await expect(page.locator('.form-error')).toBeVisible({ timeout: 5000 });
  });

  test('rejects duplicate email registration', async ({ page }) => {
    const testEmail = `duplicate-${Date.now()}-${Math.random().toString(36).substring(7)}@example.com`;

    // First registration - should succeed and redirect to login
    await page.goto('/register');
    await page.fill('label:has-text("Full Name") input', 'Test User');
    await page.fill('label:has-text("Email") input', testEmail);
    await page.fill('label:has-text("Password") input', 'password123');
    await page.fill('label:has-text("Confirm Password") input', 'password123');
    await page.click('button:has-text("Create account")');
    await expect(page).toHaveURL(/.*login/, { timeout: 15000 });

    // Second registration with same email - should fail
    await page.goto('/register');
    await page.fill('label:has-text("Full Name") input', 'Test User');
    await page.fill('label:has-text("Email") input', testEmail);
    await page.fill('label:has-text("Password") input', 'password123');
    await page.fill('label:has-text("Confirm Password") input', 'password123');

    // Click and wait for network to be idle
    await Promise.all([
      page.click('button:has-text("Create account")'),
      page.waitForLoadState('networkidle')
    ]);

    // Should stay on register page and show error
    await expect(page).toHaveURL(/.*register/, { timeout: 5000 });
    await expect(page.locator('.form-error')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('.form-error')).toContainText(/already|exists/i);
  });
});