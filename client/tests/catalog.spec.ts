import { test, expect } from '@playwright/test';
import type { CatalogItem, CurrentUserIdentity } from '../src/api/catalog';
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

function mockSubscriptionCatalogApi(
  page: import('@playwright/test').Page,
  items: CatalogItem[],
  subscribedGroups: string[],
  user: string | null = 'dev@example.com',
) {
  return page.route('**/catalog', (route) => {
    if (route.request().url().endsWith('/catalog')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          items,
          server: MOCK_SERVER,
          subscriptions_enabled: true,
          user,
          me: {
            email: user,
            authenticated: user !== null,
          },
          subscribed_groups: subscribedGroups,
          available_groups: ['team-a', 'team-b'],
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

  test('shows group subscription controls for signed-in users', async ({ page }) => {
    await mockSubscriptionCatalogApi(
      page,
      [
        {
          ...MOCK_ITEMS[0],
          group: 'team-a',
          subscribed: true,
          subscription_state: 'group',
        },
        {
          ...MOCK_ITEMS[1],
          group: 'team-a',
          subscribed: false,
          subscription_state: 'excluded',
        },
        {
          ...MOCK_ITEMS[2],
          group: 'team-b',
          subscribed: false,
          subscription_state: 'none',
        },
      ],
      ['team-a'],
    );

    await page.goto('/');

    await expect(page.getByText('Skill groups')).toBeVisible();
    await expect(page.getByRole('checkbox', { name: 'Subscribe to all in team-a' })).toBeVisible();
    await expect(page.getByRole('checkbox', { name: 'Subscribe to all in team-b' })).toBeVisible();
    await expect(page.getByRole('checkbox', { name: 'Subscribe to all in team-a' })).toHaveJSProperty('indeterminate', true);
    await expect(page.getByRole('checkbox', { name: 'Subscribe to all in team-b' })).not.toBeChecked();
  });

  test('updates item subscription checkbox immediately after subscribe', async ({ page }) => {
    const requests: string[] = [];
    await mockSubscriptionCatalogApi(
      page,
      MOCK_ITEMS.map((item) => ({
        ...item,
        subscribed: false,
        subscription_state: 'none',
      })),
      [],
    );
    await page.route('**/api/subscriptions', async (route) => {
      if (route.request().method() !== 'POST') return route.continue();
      requests.push(route.request().postData() ?? '');
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: '{"status":"subscribed"}',
      });
    });

    await page.goto('/');

    const checkbox = page.getByRole('checkbox', { name: 'Subscribe to hello-world' });
    await expect(checkbox).not.toBeChecked();
    await checkbox.click();

    await expect(checkbox).toBeChecked();
    await expect.poll(() => requests.length).toBe(1);
    expect(JSON.parse(requests[0])).toEqual({
      item_type: 'skill',
      item_name: 'hello-world',
    });
  });

  test('shows disabled group subscription controls without identity', async ({ page }) => {
    await mockSubscriptionCatalogApi(
      page,
      [
        {
          ...MOCK_ITEMS[0],
          group: 'team-a',
          subscribed: false,
          subscription_state: 'none',
        },
        {
          ...MOCK_ITEMS[1],
          group: 'team-b',
          subscribed: false,
          subscription_state: 'none',
        },
      ],
      [],
      null,
    );

    await page.goto('/');

    await expect(page.getByText('Skill groups')).toBeVisible();
    await expect(page.getByRole('checkbox', { name: 'Subscribe to all in team-a' })).toBeDisabled();
    await expect(page.getByRole('checkbox', { name: 'Subscribe to all in team-b' })).toBeDisabled();
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
