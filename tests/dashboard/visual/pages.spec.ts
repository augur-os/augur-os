import { test, expect } from '@playwright/test';

const PAGES = [
  { name: 'home', path: '/' },
  { name: 'browse', path: '/browse' },
  { name: 'workspace', path: '/workspace' },
  { name: 'workspace-memory', path: '/workspace/memory' },
  { name: 'settings', path: '/settings' },
];

for (const page of PAGES) {
  test(`dashboard surface smoke: ${page.name} page`, async ({ page: browserPage }) => {
    const response = await browserPage.goto(page.path);
    await browserPage.waitForLoadState('networkidle');

    expect(response?.status()).toBeLessThan(400);
    await expect(browserPage.locator('body')).toBeVisible();
    await expect(browserPage.getByText(/failed to load chunk/i)).toHaveCount(0);
    await expect(browserPage.getByText(/page not available/i)).toHaveCount(0);
  });
}
