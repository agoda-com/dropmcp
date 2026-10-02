import { test, expect, type Page } from '@playwright/test';
import {
  MOCK_ITEMS,
  MOCK_MEMORIES,
  MOCK_MEMORY_DETAIL,
  MOCK_MEMORY_REPORTS,
  MOCK_MEMORY_STATS,
  MOCK_SERVER,
} from './fixtures';
import type { MemoryListItem } from '../src/api/memory';

function mockCatalogApi(page: Page) {
  return page.route('**/catalog', (route) => {
    if (route.request().url().endsWith('/catalog')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          items: MOCK_ITEMS,
          server: MOCK_SERVER,
          memory_enabled: true,
        }),
      });
    }
    return route.continue();
  });
}

function filterMemories(items: MemoryListItem[], query: URLSearchParams): MemoryListItem[] {
  const search = query.get('search')?.toLowerCase();
  const repo = query.get('repo');
  const language = query.get('language');
  const kind = query.get('kind');
  const status = query.get('status');
  const hidden = query.get('hidden');
  const sort = query.get('sort') ?? 'confirmations';
  const matched = items.filter((item) => {
    if (repo && item.repo !== repo) return false;
    if (language && item.language !== language) return false;
    if (kind && item.kind !== kind) return false;
    if (status && item.status !== status) return false;
    if (hidden === 'true' && !item.hidden) return false;
    if (hidden === 'false' && item.hidden) return false;
    if (search && !item.title.toLowerCase().includes(search)) return false;
    return true;
  });
  return matched.sort((left, right) => {
    if (sort === 'recent') {
      return (right.display_confirmed_at ?? '').localeCompare(
        left.display_confirmed_at ?? '',
      );
    }
    return right.confirmations - left.confirmations;
  });
}

function facets(items: MemoryListItem[]) {
  const values = (pick: (item: MemoryListItem) => string | null) =>
    [...new Set(items.map(pick).filter((value): value is string => Boolean(value)))].sort();
  return {
    repos: values((item) => item.repo),
    languages: values((item) => item.language),
    kinds: values((item) => item.kind),
  };
}

function mockMemoryApi(page: Page) {
  const state = MOCK_MEMORIES.map((item) => ({ ...item }));
  return page.route('**/api/memory**', (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;

    if (request.method() === 'GET' && path.endsWith('/api/memory/stats')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ periods: MOCK_MEMORY_STATS }),
      });
    }

    if (request.method() === 'GET' && path.endsWith('/api/memory/reports')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ items: MOCK_MEMORY_REPORTS }),
      });
    }

    if (request.method() === 'GET' && path.endsWith('/api/memory')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          items: filterMemories(state, url.searchParams),
          ...facets(MOCK_MEMORIES),
        }),
      });
    }

    const key = decodeURIComponent(path.split('/').pop() ?? '');
    if (request.method() === 'DELETE') {
      const index = state.findIndex((item) => item.key === key);
      if (index >= 0) state.splice(index, 1);
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ deleted: key }),
      });
    }

    if (request.method() === 'GET') {
      const item = state.find((memory) => memory.key === key);
      if (!item) {
        return route.fulfill({
          status: 404,
          contentType: 'application/json',
          body: JSON.stringify({ error: 'not found' }),
        });
      }
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          memory: { ...MOCK_MEMORY_DETAIL, ...item },
          reports: MOCK_MEMORY_REPORTS.filter((report) => report.memory_key === key),
        }),
      });
    }

    return route.continue();
  });
}

test.describe('Memory page', () => {
  test('lists, filters, opens details, and deletes after confirm', async ({ page }) => {
    await mockCatalogApi(page);
    await mockMemoryApi(page);
    await page.goto('/memory');

    await expect(page.getByRole('heading', { name: 'Memory' })).toBeVisible();
    await expect(page.getByRole('link', { name: 'Memory' })).toBeVisible();
    await expect(page.getByText('Validation stays HTTP 200')).toBeVisible();
    await expect(page.getByText('Ledger rounds half away from zero')).toBeVisible();
    await expect(
      page.getByRole('article', { name: 'Ledger rounds half away from zero' }),
    ).toContainText('Hidden');
    await expect(page.getByRole('article', { name: 'Last 7 days' })).toContainText('50%');
    await expect(page.getByText('Retries are not always safe.')).toBeVisible();
    await expect(page.getByText('Unkeyed')).toBeVisible();
    await expect(page.getByText('Candidates MEM-PAY001')).toBeVisible();

    await page.getByRole('group', { name: 'Visibility' }).getByRole('button', { name: 'Hidden' }).click();
    await expect(page.getByText('Validation stays HTTP 200')).toBeHidden();
    await expect(page.getByText('Ledger rounds half away from zero')).toBeVisible();

    await page.getByRole('group', { name: 'Visibility' }).getByRole('button', { name: 'All' }).click();
    await page.getByPlaceholder('Search title or body...').fill('Validation');
    await expect(page.getByText('Ledger rounds half away from zero')).toBeHidden();
    await expect(page.getByRole('button', { name: 'Validation stays HTTP 200' })).toBeVisible();

    await page.getByRole('button', { name: 'Validation stays HTTP 200' }).click();
    const details = page.getByRole('region', { name: 'Memory details' });
    await expect(details).toContainText('Check the error body; the status code stays 200.');
    await expect(details).toContainText('A failing request still answered 200.');
    await expect(details).toContainText('The status is now 422.');

    await page.getByRole('button', { name: 'Delete' }).click();
    await expect(page.getByText('Delete this memory?')).toBeVisible();
    await expect(page.getByRole('button', { name: 'Validation stays HTTP 200' })).toBeVisible();

    const deleteResponse = page.waitForResponse(
      (response) =>
        response.request().method() === 'DELETE' &&
        response.url().includes('/api/memory/MEM-PAY001') &&
        response.ok(),
    );
    await page.getByRole('button', { name: 'Confirm delete' }).click();
    await deleteResponse;
    await expect(page.getByRole('button', { name: 'Validation stays HTTP 200' })).toHaveCount(0);
    await expect(page.getByRole('region', { name: 'Memory details' })).toHaveCount(0);
    await expect(page.getByText('No memories.')).toBeVisible();
  });
});
