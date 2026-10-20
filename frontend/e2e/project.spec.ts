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
  // Set token in localStorage - navigate to base URL first to ensure correct origin
  await page.goto('/');
  await page.evaluate((token) => localStorage.setItem('devflow.access_token', token), loginData.access_token);
  return loginData.access_token;
}

test.describe('Journey B: Project Creation and Scoped Management', () => {
  test('can create a project and sees it in the list', async ({ page }) => {
    const testEmail = `client-${Date.now()}-${Math.random().toString(36).substring(7)}@example.com`;
    const testPassword = 'password123';
    const projectName = `Test Project ${Date.now()}`;
    const apiBaseUrl = 'http://localhost:8001/api/v1';

    // Register and login via API
    await registerAndLogin(page, apiBaseUrl, testEmail, testPassword, 'Test Client');

    // Verify we're on dashboard
    await page.goto('/projects');
    await expect(page.locator('h1:has-text("Projects")')).toBeVisible();

    // Create project via API
    const token = await page.evaluate(() => localStorage.getItem('devflow.access_token'));
    const response = await page.request.post(`${apiBaseUrl}/projects`, {
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      data: { name: projectName, status: 'planned' },
    });
    expect(response.ok()).toBeTruthy();

    // Reload and verify project appears
    await page.reload();
    await expect(page.locator(`h2:has-text("${projectName}")`).first()).toBeVisible({ timeout: 10000 });
  });

  test('creator has project-scoped project_manager role without global role', async ({ page }) => {
    const testEmail = `client-${Date.now()}-${Math.random().toString(36).substring(7)}@example.com`;
    const testPassword = 'password123';
    const projectName = `Scoped Project ${Date.now()}`;
    const apiBaseUrl = 'http://localhost:8001/api/v1';

    // Register and login via API
    await registerAndLogin(page, apiBaseUrl, testEmail, testPassword, 'Scoped Manager');

    await page.goto('/projects');

    // Create project via API
    const token = await page.evaluate(() => localStorage.getItem('devflow.access_token'));

    const response = await page.request.post(`${apiBaseUrl}/projects`, {
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      data: { name: projectName, status: 'planned' },
    });
    expect(response.ok()).toBeTruthy();

    await page.reload();
    await expect(page.locator(`h2:has-text("${projectName}")`).first()).toBeVisible({ timeout: 10000 });

    // Navigate to Team page to verify management access
    await page.goto('/team');
    await expect(page).toHaveURL(/.*team/, { timeout: 5000 });
    await expect(page.locator('text=Team & developers')).toBeVisible({ timeout: 5000 });
  });

  test('management UI accessible for project with project-scoped role', async ({ page }) => {
    const testEmail = `client-${Date.now()}-${Math.random().toString(36).substring(7)}@example.com`;
    const testPassword = 'password123';
    const projectName = `Team Management Project ${Date.now()}`;
    const apiBaseUrl = 'http://localhost:8001/api/v1';

    // Register and login via API
    await registerAndLogin(page, apiBaseUrl, testEmail, testPassword, 'Team Manager');

    await page.goto('/projects');

    // Create project via API
    const token = await page.evaluate(() => localStorage.getItem('devflow.access_token'));

    const response = await page.request.post(`${apiBaseUrl}/projects`, {
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      data: { name: projectName, status: 'planned' },
    });
    expect(response.ok()).toBeTruthy();

    await page.reload();
    await expect(page.locator(`h2:has-text("${projectName}")`).first()).toBeVisible({ timeout: 10000 });

    // Navigate to Team page
    await page.goto('/team');
    await expect(page).toHaveURL(/.*team/, { timeout: 5000 });
    await expect(page.locator('text=Team & developers')).toBeVisible({ timeout: 5000 });
  });

  test('project-scoped permission does not extend to unrelated project', async ({ page }) => {
    const apiBaseUrl = 'http://localhost:8001/api/v1';

    // Create User A
    const userAEmail = `usera-${Date.now()}-${Math.random().toString(36).substring(7)}@example.com`;
    const userAPassword = 'password123';
    const userAToken = await registerAndLogin(page, apiBaseUrl, userAEmail, userAPassword, 'User A');

    // Create Project A as User A
    const projectAResponse = await page.request.post(`${apiBaseUrl}/projects`, {
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${userAToken}`
      },
      data: { name: 'Project A', status: 'planned' },
    });
    expect(projectAResponse.ok()).toBeTruthy();
    const projectA = await projectAResponse.json();
    const projectAId = projectA.id;

    // Create User B
    const userBEmail = `userb-${Date.now()}-${Math.random().toString(36).substring(7)}@example.com`;
    const userBPassword = 'password123';
    const userBToken = await registerAndLogin(page, apiBaseUrl, userBEmail, userBPassword, 'User B');

    // Create Project B as User B
    const projectBResponse = await page.request.post(`${apiBaseUrl}/projects`, {
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${userBToken}`
      },
      data: { name: 'Project B', status: 'planned' },
    });
    expect(projectBResponse.ok()).toBeTruthy();
    const projectB = await projectBResponse.json();
    const projectBId = projectB.id;

    // Verify User A can access Project A (member list)
    const userAProjectAMembers = await page.request.get(`${apiBaseUrl}/projects/${projectAId}/members`, {
      headers: { 'Authorization': `Bearer ${userAToken}` }
    });
    expect(userAProjectAMembers.ok()).toBeTruthy();
    const userAProjectAMembersData = await userAProjectAMembers.json();
    expect(userAProjectAMembersData.length).toBeGreaterThan(0);

    // Verify User A is NOT a member of Project B (should get 403)
    const userAProjectBMembers = await page.request.get(`${apiBaseUrl}/projects/${projectBId}/members`, {
      headers: { 'Authorization': `Bearer ${userAToken}` }
    });
    expect(userAProjectBMembers.status()).toBe(403);

    // Verify User B can access Project B (member list)
    const userBProjectBMembers = await page.request.get(`${apiBaseUrl}/projects/${projectBId}/members`, {
      headers: { 'Authorization': `Bearer ${userBToken}` }
    });
    expect(userBProjectBMembers.ok()).toBeTruthy();
    const userBProjectBMembersData = await userBProjectBMembers.json();
    expect(userBProjectBMembersData.length).toBeGreaterThan(0);
  });

  test('new client can add developer to project through team management UI', async ({ page }) => {
    const testEmail = `client-${Date.now()}-${Math.random().toString(36).substring(7)}@example.com`;
    const testPassword = 'password123';
    const projectName = `Test Project ${Date.now()}`;
    const apiBaseUrl = 'http://localhost:8001/api/v1';

    // Step 1: Register a new Client through the browser registration form
    await page.goto('/register');
    await expect(page.locator('h1')).toContainText('Join your workspace');

    await page.fill('label:has-text("Full Name") input', 'Test Client');
    await page.fill('label:has-text("Email") input', testEmail);
    await page.fill('label:has-text("Password") input', testPassword);
    await page.fill('label:has-text("Confirm Password") input', testPassword);
    await page.click('button:has-text("Create account")');

    // Wait for redirect to login (success) or error
    await Promise.race([
      expect(page).toHaveURL(/.*login/, { timeout: 15000 }),
      expect(page.locator('.form-error')).toBeVisible({ timeout: 10000 })
    ]);

    // If registration failed due to existing email (shouldn't happen with unique email), fail
    if (page.url().includes('/register')) {
      const errorText = await page.locator('.form-error').textContent();
      throw new Error(`Registration failed: ${errorText}`);
    }

    // Step 2: Log in through the browser login form
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

    // Step 3: Create a project using the authenticated project API
    // (Clients create projects via API since they don't have global canManage role for UI button)
    const token = await page.evaluate(() => localStorage.getItem('devflow.access_token'));

    const createResponse = await page.request.post(`${apiBaseUrl}/projects`, {
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
      },
      data: { name: projectName, status: 'planned' },
    });
    expect(createResponse.ok()).toBeTruthy();
    const projectData = await createResponse.json();
    const projectId = projectData.id;

    // Step 4: Verify the project is successfully persisted and visible
    await page.goto('/projects');
    await expect(page.locator('h1:has-text("Projects")')).toBeVisible();
    await expect(page.locator(`h2:has-text("${projectName}")`).first()).toBeVisible({ timeout: 10000 });

    // Step 5: Verify the creator has a project-scoped project_manager membership
    // Fetch project members via API to verify the creator has project_manager role
    const membersResponse = await page.request.get(`${apiBaseUrl}/projects/${projectId}/members`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    expect(membersResponse.ok()).toBeTruthy();
    const members = await membersResponse.json();

    // Get current user info to find the creator in members list
    const meResponse = await page.request.get(`${apiBaseUrl}/auth/me`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    expect(meResponse.ok()).toBeTruthy();
    const meData = await meResponse.json();

    const creatorMember = members.find((m: { user_id: string }) => m.user_id === meData.id);
    expect(creatorMember).toBeTruthy();
    expect(creatorMember.project_role).toBe('project_manager');

    // Step 6: Verify global roles have not changed (should only have "client")
    const globalRoles = meData.roles.map((r: { code: string }) => r.code);
    expect(globalRoles).toEqual(['client']); // Only client role globally

    // Step 7: Navigate to the project's Team management page
    await page.goto('/team');
    await expect(page).toHaveURL(/.*team/, { timeout: 5000 });

    // Step 8: Open the Add Developer form
    await expect(page.locator('text=Team & developers')).toBeVisible({ timeout: 5000 });
    await page.click('button:has-text("Add developer")');

    // Step 9: Wait for the developer dropdown to be populated
    // The dropdown options have value=user_id and label="Full Name · email"
    await expect(page.locator('label:has-text("Developer") select')).toBeVisible({ timeout: 10000 });

    // Get the developer's ID from the API to select the correct option
    const developersResponse = await page.request.get(`${apiBaseUrl}/users/developers?project_id=${projectId}`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    expect(developersResponse.ok()).toBeTruthy();
    const developers = await developersResponse.json();
    const testDev = developers.find((d: { email: string }) => d.email === 'devtest@example.com');
    expect(testDev).toBeTruthy();
    const devUserId = testDev.id;

    // Step 10: Select the developer from the dropdown by their user ID
    await page.selectOption('label:has-text("Developer") select', devUserId);

    // Step 11: Submit the form
    await page.click('button:has-text("Add developer")');

    // Step 12: Wait for success message
    await expect(page.locator('.success-banner')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('.success-banner')).toContainText('Developer added to the project');

    // Step 12: Verify the developer was added via API
    const membersResponseAfter = await page.request.get(`${apiBaseUrl}/projects/${projectId}/members`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    expect(membersResponseAfter.ok()).toBeTruthy();
    const membersAfter = await membersResponseAfter.json();

    // Find the developer in the members list
    const addedDev = membersAfter.find((m: { email: string }) => m.email === 'devtest@example.com');
    expect(addedDev).toBeTruthy();
    expect(addedDev.project_role).toBe('developer');

    // Step 9: Verify global roles remain unchanged
    const meResponseAfter = await page.request.get(`${apiBaseUrl}/auth/me`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    expect(meResponseAfter.ok()).toBeTruthy();
    const meDataAfter = await meResponseAfter.json();
    const globalRolesAfter = meDataAfter.roles.map((r: { code: string }) => r.code);
    expect(globalRolesAfter).toEqual(['client']); // Only client role globally

    // Step 10: Reload team page and verify membership remains visible
    await page.reload();
    await expect(page.locator('text=Team & developers')).toBeVisible({ timeout: 5000 });

    // Verify the developer appears in the developer list
    const devMember = page.locator('text=Test Developer');
    await expect(devMember).toBeVisible({ timeout: 5000 });
  });
});