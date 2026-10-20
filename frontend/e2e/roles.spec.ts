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
  // Set token in localStorage
  await page.goto('/');
  await page.evaluate((token) => localStorage.setItem('devflow.access_token', token), loginData.access_token);
  return loginData.access_token;
}

async function createProject(page, apiBaseUrl, token, projectName) {
  const response = await page.request.post(`${apiBaseUrl}/projects`, {
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`
    },
    data: { name: projectName, status: 'planned' },
  });
  expect(response.ok()).toBeTruthy();
  return response.json();
}

test('global administrator has cross-project access', async ({ page }) => {
    const adminEmail = `admin@example.com`;
    const adminPassword = 'password123';

    // Login as pre-seeded admin user
    await page.goto('/login');
    await page.fill('label:has-text("Email") input', adminEmail);
    await page.fill('label:has-text("Password") input', adminPassword);
    await page.click('button:has-text("Sign in")');
    await expect(page).toHaveURL('/', { timeout: 10000 });

    const apiBaseUrl = 'http://localhost:8001/api/v1';
    const token = await page.evaluate(() => localStorage.getItem('devflow.access_token'));

    // Verify admin has global admin role
    const meResponse = await page.request.get(`${apiBaseUrl}/auth/me`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    expect(meResponse.ok()).toBeTruthy();
    const meData = await meResponse.json();
    const globalRoles = meData.roles.map((r: { code: string }) => r.code);
    expect(globalRoles).toContain('admin');

    // Create a project owned by a different user to test cross-project access
    const otherEmail = `other-${Date.now()}@example.com`;
    const otherPassword = 'password123';
    await page.request.post(`${apiBaseUrl}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      data: { full_name: 'Other User', email: otherEmail, password: otherPassword },
    });
    const otherLogin = await fetch(`${apiBaseUrl}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email: otherEmail, password: otherPassword })
    });
    const otherLoginData = await otherLogin.json();

    // Create project as other user
    const otherProject = await page.request.post(`${apiBaseUrl}/projects`, {
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${otherLoginData.access_token}`
      },
      data: { name: 'Other User Project', status: 'planned' },
    });
    expect(otherProject.ok()).toBeTruthy();
    const otherProjectData = await otherProject.json();
    const otherProjectId = otherProjectData.id;

    // Admin should have cross-project access to the other user's project
    const adminProjectMembers = await page.request.get(`${apiBaseUrl}/projects/${otherProjectId}/members`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    expect(adminProjectMembers.ok()).toBeTruthy();
    // Admin can access members list via global admin role (not as project member)
    // The members list shows explicit project members, not global admins
    const adminMembers = await adminProjectMembers.json();
    // Verify we can at least see the project owner in members
    expect(adminMembers.length).toBeGreaterThan(0);

    // Admin should be able to view the other user's project
    await page.goto(`/projects/${otherProjectId}`);
    await expect(page.locator('h1:has-text("Other User Project")')).toBeVisible({ timeout: 5000 });

    // Admin should be able to access team management for other user's project
    await page.goto('/team');
    await expect(page).toHaveURL(/.*team/, { timeout: 5000 });
    await expect(page.locator('text=Team & developers')).toBeVisible({ timeout: 5000 });
    await expect(page.locator('button:has-text("Add developer")')).toBeVisible();
  });


test.describe('role-based access control', () => {
test('global project manager needs project access for management', async ({ page }) => {
  // This test would require setting up a user with global project_manager role
  // For now, we verify that a regular user who creates a project gets project-scoped management
  // A global project_manager role would need to be assigned via database or admin UI
  // The backend policy requires project access + global role for management
  test.skip('Requires global project_manager role assignment via admin UI');
});

test('global team lead needs project access for management', async ({ page }) => {
  // Similar to project_manager - team_lead needs project access
  test.skip('Requires global team_lead role assignment via admin UI');
});

test('non-member cannot access project management', async ({ page }) => {
  const testEmail = `nonmember-${Date.now()}@example.com`;
  const testPassword = 'password123';
  const apiBaseUrl = 'http://localhost:8001/api/v1';

  // Create project owner
  const ownerEmail = `owner-${Date.now()}@example.com`;
  const ownerPassword = 'password123';
  const ownerToken = await registerAndLogin(page, apiBaseUrl, ownerEmail, ownerPassword, 'Project Owner');

  // Create project as owner
  const project = await createProject(page, apiBaseUrl, ownerToken, 'Private Project');
  const projectId = project.id;

  // Register a non-member user
  const nonMemberEmail = `nonmember-${Date.now()}@example.com`;
  const nonMemberPassword = 'password123';
  const nonMemberToken = await registerAndLogin(page, apiBaseUrl, nonMemberEmail, nonMemberPassword, 'Non Member');

  // Non-member tries to access project members - should fail
  const membersResponse = await page.request.get(`${apiBaseUrl}/projects/${projectId}/members`, {
    headers: { 'Authorization': `Bearer ${nonMemberToken}` }
  });
  expect(membersResponse.status()).toBe(403);

  // Non-member tries to access team page - should be denied
  await page.goto('/team');
  // Non-member should not see team management controls for this project
  // The project selector should not show the private project, or access should be denied
  await expect(page.locator('text=Team & developers')).not.toBeVisible({ timeout: 5000 });
  await expect(page.locator('button:has-text("Add developer")')).not.toBeVisible({ timeout: 5000 });
});

test('project-scoped project_manager can manage their project', async ({ page }) => {
  const testEmail = `scoped-${Date.now()}@example.com`;
  const testPassword = 'password123';
  const apiBaseUrl = 'http://localhost:8001/api/v1';

  await page.goto('/register');
  await page.fill('label:has-text("Full Name") input', 'Scoped Manager');
  await page.fill('label:has-text("Email") input', testEmail);
  await page.fill('label:has-text("Password") input', testPassword);
  await page.fill('label:has-text("Confirm Password") input', testPassword);
  await page.click('button:has-text("Create account")');
  await expect(page.locator('.success-banner')).toBeVisible({ timeout: 10000 });
  await expect(page).toHaveURL(/.*login/, { timeout: 15000 });

  await page.fill('label:has-text("Email") input', testEmail);
  await page.fill('label:has-text("Password") input', testPassword);
  await page.click('button:has-text("Sign in")');
  await expect(page).toHaveURL('/', { timeout: 10000 });

  // Create project via API
  const token = await page.evaluate(() => localStorage.getItem('devflow.access_token'));
  const projectId = (await createProject(page, apiBaseUrl, token, 'My Scoped Project')).id;

  // Verify project-scoped project_manager role via API
  const meResponse = await page.request.get(`${apiBaseUrl}/auth/me`, {
    headers: { 'Authorization': `Bearer ${token}` }
  });
  expect(meResponse.ok()).toBeTruthy();
  const meData = await meResponse.json();

  const membersResponse = await page.request.get(`${apiBaseUrl}/projects/${projectId}/members`, {
    headers: { 'Authorization': `Bearer ${token}` }
  });
  expect(membersResponse.ok()).toBeTruthy();
  const members = await membersResponse.json();
  const creatorMember = members.find((m: { user_id: string }) => m.user_id === meData.id);
  expect(creatorMember).toBeTruthy();
  expect(creatorMember.project_role).toBe('project_manager');

  // Navigate to project detail and verify team page access
  await page.goto(`/projects/${projectId}`);
  await expect(page.locator('h1:has-text("My Scoped Project")').first()).toBeVisible();

  // Navigate directly to team page (bypassing UI cache timing)
  await page.goto('/team');
  await expect(page).toHaveURL(/.*team/, { timeout: 5000 });
  await expect(page.locator('text=Team & developers')).toBeVisible({ timeout: 5000 });
  await expect(page.locator('button:has-text("Add developer")')).toBeVisible();
});

test('project creator with client global role receives project-scoped management access', async ({ page }) => {
  // Create a regular user (client role by default)
  const testEmail = `member-${Date.now()}@example.com`;
  const testPassword = 'password123';
  const apiBaseUrl = 'http://localhost:8001/api/v1';

  await page.goto('/register');
  await page.fill('label:has-text("Full Name") input', 'Regular Member');
  await page.fill('label:has-text("Email") input', testEmail);
  await page.fill('label:has-text("Password") input', testPassword);
  await page.fill('label:has-text("Confirm Password") input', testPassword);
  await page.click('button:has-text("Create account")');
  await expect(page.locator('.success-banner')).toBeVisible({ timeout: 10000 });
  await expect(page).toHaveURL(/.*login/, { timeout: 15000 });

  await page.fill('label:has-text("Email") input', testEmail);
  await page.fill('label:has-text("Password") input', testPassword);
  await page.click('button:has-text("Sign in")');
  await expect(page).toHaveURL('/', { timeout: 10000 });

  // Create project via API
  const token = await page.evaluate(() => localStorage.getItem('devflow.access_token'));
  const projectId = (await createProject(page, apiBaseUrl, token, 'Member Project')).id;

  // Verify global roles have not changed (should only have "client")
  const meResponse = await page.request.get(`${apiBaseUrl}/auth/me`, {
    headers: { 'Authorization': `Bearer ${token}` }
  });
  expect(meResponse.ok()).toBeTruthy();
  const meData = await meResponse.json();
  const globalRoles = meData.roles.map((r: { code: string }) => r.code);
  expect(globalRoles).toEqual(['client']); // Only client role globally

  // Verify project-scoped project_manager role via API
  const membersResponse = await page.request.get(`${apiBaseUrl}/projects/${projectId}/members`, {
    headers: { 'Authorization': `Bearer ${token}` }
  });
  expect(membersResponse.ok()).toBeTruthy();
  const members = await membersResponse.json();
  const creatorMember = members.find((m: { user_id: string }) => m.user_id === meData.id);
  expect(creatorMember).toBeTruthy();
  expect(creatorMember.project_role).toBe('project_manager');
});

test('frontend visibility matches backend authorization for project-scoped roles', async ({ page }) => {
  const apiBaseUrl = 'http://localhost:8001/api/v1';

  // Create two users: one who creates a project (gets project_manager), one who doesn't
  const ownerEmail = `owner-${Date.now()}@example.com`;
  const ownerPassword = 'password123';
  const ownerToken = await registerAndLogin(page, apiBaseUrl, ownerEmail, ownerPassword, 'Project Owner');

  const project = await createProject(page, apiBaseUrl, ownerToken, 'Visibility Test Project');
  const projectId = project.id;

  // Verify owner (project creator) sees management UI
  await page.goto('/team');
  await expect(page).toHaveURL(/.*team/, { timeout: 5000 });
  await expect(page.locator('text=Team & developers')).toBeVisible({ timeout: 5000 });
  await expect(page.locator('button:has-text("Add developer")')).toBeVisible({ timeout: 5000 });

  // Create a non-member user
  const nonMemberEmail = `nonmember-${Date.now()}@example.com`;
  const nonMemberPassword = 'password123';
  const nonMemberToken = await registerAndLogin(page, apiBaseUrl, nonMemberEmail, nonMemberPassword, 'Non Member');

  // Verify non-member does NOT see management UI
  await page.goto('/team');
  await expect(page.locator('text=Team & developers')).not.toBeVisible({ timeout: 5000 });
  await expect(page.locator('button:has-text("Add developer")')).not.toBeVisible({ timeout: 5000 });
});
});