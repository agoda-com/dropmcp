import { test, expect } from '@playwright/test';
import type { CurrentUserIdentity } from '../src/api/catalog';
import { MOCK_ITEMS, MOCK_SERVER } from './fixtures';

function mockCatalogApi(
  page: import('@playwright/test').Page,
  me?: CurrentUserIdentity,
) {
  return page.route('**/catalog', (route) => {
    if (route.request().url().endsWith('/catalog')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          items: MOCK_ITEMS,
          server: MOCK_SERVER,
          ...(me ? { me, user: me.email } : {}),
        }),
      });
    }
    return route.continue();
  });
}

function mockDetailApi(page: import('@playwright/test').Page) {
  return page.route('**/catalog/**', (route) => {
    const url = route.request().url();
    const match = url.match(/\/catalog\/(\w+)\/([\w-]+)$/);
    if (match) {
      const [, type, name] = match;
      const item = MOCK_ITEMS.find((i) => i.type === type && i.name === name);
      if (item) {
        return route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(item),
        });
      }
      return route.fulfill({ status: 404, body: '{"error":"not found"}' });
    }
    return route.continue();
  });
}

test.describe('Catalog Page', () => {
  test('renders grid with skill cards', async ({ page }) => {
    await mockCatalogApi(page);
    await page.goto('/');
    await page.waitForSelector('a[href*="/skill/"]');
    await expect(page.locator('a[href*="/skill/"]')).toHaveCount(2);
    await expect(page.getByRole('heading', { level: 1, name: MOCK_SERVER.name })).toBeVisible();
    await expect(page).toHaveScreenshot('catalog-grid.png');
  });

  test('shows empty state when search has no results', async ({ page }) => {
    await mockCatalogApi(page);
    await page.goto('/');
    await page.waitForSelector('a[href*="/skill/"]');
    await page.fill('input[type="search"]', 'zzzznonexistent');
    await expect(page.getByText('No matches')).toBeVisible();
    await expect(page).toHaveScreenshot('catalog-empty.png');
  });

  test('install panel is expanded by default', async ({ page }) => {
    await mockCatalogApi(page);
    await page.goto('/');
    await expect(page.getByText('Get Started — Install')).toBeVisible();
    await expect(page.getByRole('tab', { name: 'Cursor' })).toBeVisible();
    await expect(page).toHaveScreenshot('install-panel.png');
  });

  test('shows signed-in user in the footer', async ({ page }) => {
    await mockCatalogApi(page, {
      email: 'dev@example.com',
      authenticated: true,
    });
    await page.goto('/');
    await expect(page.locator('footer')).toContainText(
      'Signed in as dev@example.com',
    );
  });

  test('does not show identity line for anonymous users', async ({ page }) => {
    await mockCatalogApi(page, {
      email: null,
      authenticated: false,
    });
    await page.goto('/');
    await expect(page.locator('footer')).not.toContainText('Signed in as');
  });
});

test.describe('Detail Page', () => {
  test('renders skill detail page', async ({ page }) => {
    await mockDetailApi(page);
    await page.goto('/skill/hello-world');
    await expect(page.getByRole('heading', { name: 'Hello World' })).toBeVisible();
    await expect(page.getByText('A minimal example skill')).toBeVisible();
    await expect(page).toHaveScreenshot('detail-skill.png');
  });
});
