import { test, expect, type Page } from '@playwright/test';
import { MOCK_FEEDBACK, MOCK_ITEMS, MOCK_SERVER } from './fixtures';
import type { FeedbackItem } from '../src/api/feedback';

function mockCatalogApi(page: Page) {
  return page.route('**/catalog', (route) => {
    if (route.request().url().endsWith('/catalog')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ items: MOCK_ITEMS, server: MOCK_SERVER }),
      });
    }
    return route.continue();
  });
}

function filterFeedback(items: FeedbackItem[], query: URLSearchParams): FeedbackItem[] {
  const search = query.get('search')?.toLowerCase();
  const status = query.get('status');
  const feedbackType = query.get('feedback_type');
  const model = query.get('model');
  const client = query.get('client');
  return items.filter((item) => {
    if (status && item.status !== status) return false;
    if (feedbackType && (item.feedback_type ?? 'correction') !== feedbackType) return false;
    if (model && item.model !== model) return false;
    if (client && item.client !== client) return false;
    if (search) {
      const haystack = `${item.feedback} ${item.better_instruction}`.toLowerCase();
      if (!haystack.includes(search)) return false;
    }
    return true;
  });
}

function mockFeedbackApi(page: Page, items: FeedbackItem[] = MOCK_FEEDBACK) {
  return page.route('**/api/feedback**', (route) => {
    const request = route.request();
    const url = new URL(request.url());

    if (request.method() === 'GET' && url.pathname.endsWith('/api/feedback')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ items: filterFeedback(items, url.searchParams) }),
      });
    }

    if (request.method() === 'PATCH') {
      const id = url.pathname.split('/').pop();
      const original = items.find((item) => item.id === id);
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ ...original, ...JSON.parse(request.postData() ?? '{}') }),
      });
    }

    return route.continue();
  });
}

test.describe('Feedback Page', () => {
  test('renders feedback cards', async ({ page }) => {
    await mockCatalogApi(page);
    await mockFeedbackApi(page);
    await page.goto('/feedback');
    await expect(page.getByRole('heading', { name: 'Agent feedback' })).toBeVisible();
    await expect(page.locator('article')).toHaveCount(MOCK_FEEDBACK.length);
    await expect(page.getByText('ui-snapshot-helper')).toBeVisible();
    await expect(page).toHaveScreenshot('feedback-list.png');
  });

  test('shows empty state when there is no feedback', async ({ page }) => {
    await mockCatalogApi(page);
    await mockFeedbackApi(page, []);
    await page.goto('/feedback');
    await expect(page.getByText('No feedback entries yet.')).toBeVisible();
    await expect(page).toHaveScreenshot('feedback-empty.png');
  });

  test('filters cards by status', async ({ page }) => {
    await mockCatalogApi(page);
    await mockFeedbackApi(page);
    await page.goto('/feedback');
    await expect(page.locator('article')).toHaveCount(MOCK_FEEDBACK.length);
    await page.getByRole('button', { name: 'actioned', exact: true }).click();
    await expect(page.locator('article')).toHaveCount(1);
    await expect(page).toHaveScreenshot('feedback-filtered-actioned.png');
  });

  test('filters and expands agent-work details', async ({ page }) => {
    await mockCatalogApi(page);
    await mockFeedbackApi(page);
    await page.goto('/feedback');
    await page.getByRole('button', { name: 'agent work', exact: true }).click();
    await expect(page.locator('article')).toHaveCount(1);

    await page.getByText('Details').click();
    await expect(page.getByText('scripts/stabilize_feedback_snapshots.ts')).toBeVisible();
    await expect(page.getByText('stableFeedback')).toBeVisible();
  });
});
