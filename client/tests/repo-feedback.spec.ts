import { test, expect, type Page } from '@playwright/test';
import { MOCK_ITEMS, MOCK_REPO_FEEDBACK, MOCK_SERVER } from './fixtures';
import type {
  RepoFeedbackItem,
  RepoFeedbackStatus,
} from '../src/api/repoFeedback';

function mockCatalogApi(page: Page) {
  return page.route('**/catalog', (route) => {
    if (route.request().url().endsWith('/catalog')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          items: MOCK_ITEMS,
          server: MOCK_SERVER,
          feedback_enabled: true,
          repo_feedback_enabled: true,
        }),
      });
    }
    return route.continue();
  });
}

function filterRepoFeedback(
  items: RepoFeedbackItem[],
  query: URLSearchParams,
): RepoFeedbackItem[] {
  const search = query.get('search')?.toLowerCase();
  const status = query.get('status');
  const category = query.get('category');
  const repo = query.get('repo');
  const model = query.get('model');
  const client = query.get('client');
  return items.filter((item) => {
    if (status && item.status !== status) return false;
    if (category && item.category !== category) return false;
    if (repo && item.repo !== repo) return false;
    if (model && item.model !== model) return false;
    if (client && item.client !== client) return false;
    if (search) {
      const haystack = `${item.summary} ${item.impact}`.toLowerCase();
      if (!haystack.includes(search)) return false;
    }
    return true;
  });
}

function mockRepoFeedbackApi(
  page: Page,
  items: RepoFeedbackItem[] = MOCK_REPO_FEEDBACK,
) {
  const state = items.map((item) => ({ ...item }));
  return page.route('**/api/repo-feedback**', (route) => {
    const request = route.request();
    const url = new URL(request.url());

    if (request.method() === 'GET' && url.pathname.endsWith('/api/repo-feedback')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ items: filterRepoFeedback(state, url.searchParams) }),
      });
    }

    if (request.method() === 'PATCH') {
      const id = url.pathname.split('/').pop();
      const original = state.find((item) => item.id === id);
      const body = JSON.parse(request.postData() ?? '{}') as {
        status?: RepoFeedbackStatus;
        resolution_url?: string | null;
      };
      if (original) Object.assign(original, body);
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(original),
      });
    }

    return route.continue();
  });
}

test.describe('Repo Feedback Page', () => {
  test('renders and filters repo feedback cards', async ({ page }) => {
    await mockCatalogApi(page);
    await mockRepoFeedbackApi(page);
    await page.goto('/repo-feedback');

    await expect(page.getByRole('heading', { name: 'Repo feedback' })).toBeVisible();
    await expect(page.locator('article')).toHaveCount(MOCK_REPO_FEEDBACK.length);
    await expect(page.getByText('occurrences: 8')).toBeVisible();

    await page.getByRole('button', { name: 'docs gap', exact: true }).click();
    await expect(page.locator('article')).toHaveCount(1);
    await expect(page.getByText('Local setup docs do not mention')).toBeVisible();
  });

  test('expands details and saves triage state', async ({ page }) => {
    await mockCatalogApi(page);
    await mockRepoFeedbackApi(page);
    await page.goto('/repo-feedback');

    await page.getByText('Details').click();
    await expect(page.getByText('pytest tests/test_feedback.py')).toBeVisible();

    await page.locator('article').first().getByLabel('Status').selectOption('wontfix');
    await page.locator('article').first().getByRole('button', { name: 'Save' }).click();
    await page.getByRole('button', { name: 'wontfix', exact: true }).click();
    await expect(page.locator('article')).toHaveCount(1);
  });
});
