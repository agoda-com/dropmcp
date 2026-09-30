import { test, expect, type Locator, type Page } from '@playwright/test';
import { MOCK_ITEMS, MOCK_SERVER } from './fixtures';
import type {
  BenchmarkAggregate,
  BenchmarkStatus,
  BenchmarksResponse,
} from '../src/api/benchmarks';

const RUN = {
  triggered_at: 1714200000000,
  pipeline_id: '4321',
  commit_sha: 'abc1234def567',
};

function agg(
  average_score: number,
  average_threshold: number,
  passed: number,
  total: number,
  status: BenchmarkStatus,
): BenchmarkAggregate {
  return { average_score, average_threshold, passed, total, status };
}

const MOCK_BENCHMARKS: BenchmarksResponse = {
  project: 'org/skills',
  lookback_days: 60,
  generated_at: '2026-09-30T08:00:00+00:00',
  error: null,
  models: ['model-a', 'model-b'],
  test_count: 5,
  summary: {
    'model-a': {
      ...agg(80.3, 77.5, 3, 4, 'partial'),
      history: agg(92, 77.5, 18, 20, 'partial'),
    },
    'model-b': {
      ...agg(91, 77.5, 2, 2, 'pass'),
      history: agg(90, 77.5, 9, 10, 'partial'),
    },
  },
  skills: [
    {
      name: 'alpha',
      test_count: 2,
      overall: { ...agg(91.7, 80, 3, 3, 'pass'), history: agg(88, 80, 10, 12, 'partial') },
      cells: {
        'model-a': {
          ...agg(90, 80, 2, 2, 'pass'),
          ...RUN,
          history: agg(84, 80, 5, 6, 'partial'),
        },
        'model-b': {
          ...agg(95, 80, 1, 1, 'pass'),
          ...RUN,
          history: agg(95, 80, 3, 3, 'pass'),
        },
      },
      tests: [
        {
          name: 'alpha/one',
          results: {
            'model-a': {
              passed: true,
              score: 92,
              threshold: 80,
              ...RUN,
              history: agg(90, 80, 5, 6, 'partial'),
              series: [85, 88, 90, 92],
            },
            'model-b': {
              passed: true,
              score: 95,
              threshold: 80,
              ...RUN,
              history: agg(95, 80, 3, 3, 'pass'),
              series: [94, 95, 95],
            },
          },
        },
        {
          name: 'alpha/two',
          results: {
            'model-a': {
              passed: true,
              score: 88,
              threshold: 80,
              ...RUN,
              history: agg(80, 80, 4, 6, 'partial'),
              series: [70, 75, 88],
            },
          },
        },
      ],
    },
    {
      name: 'beta',
      test_count: 2,
      overall: { ...agg(76, 75, 2, 3, 'partial'), history: agg(78, 75, 6, 10, 'partial') },
      cells: {
        'model-a': {
          ...agg(70.5, 75, 1, 2, 'partial'),
          ...RUN,
          history: agg(72, 75, 3, 8, 'partial'),
        },
        'model-b': {
          ...agg(87, 75, 1, 1, 'pass'),
          ...RUN,
          history: agg(87, 75, 1, 1, 'pass'),
        },
      },
      tests: [
        {
          name: 'beta/one',
          results: {
            'model-a': {
              passed: true,
              score: 81,
              threshold: 75,
              ...RUN,
              history: agg(78, 75, 3, 4, 'partial'),
              series: [76, 79, 81],
            },
            'model-b': {
              passed: true,
              score: 87,
              threshold: 75,
              ...RUN,
              history: agg(87, 75, 1, 1, 'pass'),
              series: [87],
            },
          },
        },
        {
          name: 'beta/two',
          results: {
            'model-a': {
              passed: false,
              score: 60,
              threshold: 75,
              ...RUN,
              history: agg(66, 75, 0, 4, 'fail'),
              series: [70, 68, 60],
            },
          },
        },
      ],
    },
    {
      name: 'gamma',
      test_count: 1,
      overall: { ...agg(50, 80, 0, 1, 'fail'), history: agg(55, 80, 0, 3, 'fail') },
      cells: {
        'model-a': {
          ...agg(50, 80, 0, 1, 'fail'),
          ...RUN,
          history: agg(55, 80, 0, 3, 'fail'),
        },
      },
      tests: [
        {
          name: 'gamma/one',
          results: {
            'model-a': {
              passed: false,
              score: 50,
              threshold: 80,
              ...RUN,
              history: agg(55, 80, 0, 3, 'fail'),
              series: [60, 55, 50],
            },
          },
        },
      ],
    },
  ],
};

const SIGNED_IN = { email: 'dev@example.com', authenticated: true };
const ANONYMOUS = { email: null, authenticated: false };

function mockCatalog(
  page: Page,
  options: { benchmarks_enabled?: boolean; me?: typeof SIGNED_IN | typeof ANONYMOUS } = {},
) {
  const { benchmarks_enabled = true, me = SIGNED_IN } = options;
  return page.route('**/catalog', (route) => {
    if (route.request().url().endsWith('/catalog')) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          items: MOCK_ITEMS,
          server: MOCK_SERVER,
          feedback_enabled: false,
          benchmarks_enabled,
          me,
          user: me.email,
        }),
      });
    }
    return route.continue();
  });
}

function mockBenchmarks(
  page: Page,
  body: Partial<BenchmarksResponse> = {},
  status = 200,
) {
  return page.route('**/api/benchmarks', (route) =>
    route.fulfill({
      status,
      contentType: 'application/json',
      body: JSON.stringify(
        status === 200 ? { ...MOCK_BENCHMARKS, ...body } : body,
      ),
    }),
  );
}

async function open(page: Page, query = '') {
  await mockCatalog(page);
  await mockBenchmarks(page);
  await page.goto(`/benchmarks${query}`);
  await page.waitForSelector('tbody tr');
}

function skillRow(page: Page, name: string): Locator {
  return page.locator('tbody tr', {
    has: page.getByRole('button', { name: new RegExp(`^${name}\\b`) }),
  });
}

function headerRow(page: Page): Locator {
  return page.locator('thead tr').first();
}

function overallRow(page: Page): Locator {
  return page.locator('thead tr').nth(1);
}

async function cellIn(page: Page, row: Locator, column: string): Promise<Locator> {
  const headers = await headerRow(page).locator('th').allTextContents();
  return row.locator('> *').nth(headers.indexOf(column));
}

test.describe('Benchmarks header link', () => {
  test('is shown when benchmarks are enabled and the user is signed in', async ({ page }) => {
    await mockCatalog(page);
    await page.goto('/');

    await expect(page.getByRole('link', { name: 'Benchmarks' })).toBeVisible();
  });

  test('is hidden for anonymous users', async ({ page }) => {
    await mockCatalog(page, { me: ANONYMOUS });
    await page.goto('/');
    await page.waitForSelector('h1');

    await expect(page.getByRole('link', { name: 'Benchmarks' })).toHaveCount(0);
  });

  test('is hidden when benchmarks are disabled', async ({ page }) => {
    await mockCatalog(page, { benchmarks_enabled: false });
    await page.goto('/');
    await page.waitForSelector('h1');

    await expect(page.getByRole('link', { name: 'Benchmarks' })).toHaveCount(0);
  });

  test('navigates to the benchmarks page', async ({ page }) => {
    await mockCatalog(page);
    await mockBenchmarks(page);
    await page.goto('/');

    await page.getByRole('link', { name: 'Benchmarks' }).click();

    await expect(page).toHaveURL(/\/benchmarks$/);
    await expect(page.getByRole('heading', { name: 'Benchmarks' })).toBeVisible();
  });
});

test.describe('Benchmarks matrix', () => {
  test('lists an all-models column then models ranked by latest average', async ({ page }) => {
    await open(page);

    await expect(headerRow(page).locator('th')).toHaveText([
      'Skill',
      'All models',
      'model-b',
      'model-a',
    ]);
    await expect(page.locator('tbody tr')).toHaveCount(3);
  });

  test('shows each model overall with its delta, pass count and coverage', async ({ page }) => {
    await open(page);

    const modelB = await cellIn(page, overallRow(page), 'model-b');
    await expect(modelB).toContainText('91');
    await expect(modelB).toContainText('▲1');
    await expect(modelB).toContainText('2/2 passed · 2/5 tests');
    const modelA = await cellIn(page, overallRow(page), 'model-a');
    await expect(modelA).toContainText('80.3');
    await expect(modelA).toContainText('▼11.7');
    await expect(modelA).toContainText('3/4 passed · 4/5 tests');
  });

  test('shows each skill average across models', async ({ page }) => {
    await open(page);

    const all = await cellIn(page, skillRow(page, 'alpha'), 'All models');
    await expect(all).toContainText('91.7');
    await expect(all).toContainText('▲3.7');
    await expect(all).toContainText('3/3 passed');
  });

  test('shows score, threshold, pass ratio and delta in each cell', async ({ page }) => {
    await open(page);

    const cell = await cellIn(page, skillRow(page, 'alpha'), 'model-a');
    await expect(cell).toContainText('90');
    await expect(cell).toContainText('▲6');
    await expect(cell).toContainText('thr 80 · 2/2');
    const partial = await cellIn(page, skillRow(page, 'alpha'), 'model-b');
    await expect(partial).toContainText('thr 80 · 1/1 of 2');
  });

  test('marks a model that did not run a skill', async ({ page }) => {
    await open(page);

    await expect(await cellIn(page, skillRow(page, 'gamma'), 'model-b')).toHaveText('—');
  });

  test('colours cells by pass status', async ({ page }) => {
    await page.emulateMedia({ colorScheme: 'light' });
    await open(page);

    await expect(await cellIn(page, skillRow(page, 'alpha'), 'model-a')).toHaveCSS(
      'background-color',
      'rgb(230, 244, 234)',
    );
    await expect(await cellIn(page, skillRow(page, 'beta'), 'model-a')).toHaveCSS(
      'background-color',
      'rgb(255, 244, 214)',
    );
    await expect(await cellIn(page, skillRow(page, 'gamma'), 'model-a')).toHaveCSS(
      'background-color',
      'rgb(253, 232, 232)',
    );
  });

  test('describes the run and the average in the cell tooltip', async ({ page }) => {
    await open(page);

    const title = await (await cellIn(page, skillRow(page, 'alpha'), 'model-a')).getAttribute('title');
    expect(title).toContain('Pipeline 4321 · abc1234 · 2024-04-27');
    expect(title).toContain('60-day average 84 over 6 runs');
  });

  test('expands a skill to per-test rows with a trend line and collapses again', async ({ page }) => {
    await open(page);

    const toggle = page.getByRole('button', { name: /^alpha\b/ });
    await expect(toggle).toHaveAttribute('aria-expanded', 'false');
    await expect(page.locator('tbody tr')).toHaveCount(3);

    await toggle.click();

    await expect(toggle).toHaveAttribute('aria-expanded', 'true');
    await expect(page.locator('tbody tr')).toHaveCount(5);
    const one = page.locator('tbody tr', { hasText: /^one/ });
    await expect(await cellIn(page, one, 'model-a')).toHaveText('92 / 80 ✓');
    await expect(await cellIn(page, one, 'model-b')).toHaveText('95 / 80 ✓');
    const two = page.locator('tbody tr', { hasText: /^two/ });
    await expect(await cellIn(page, two, 'model-b')).toHaveText('—');
    await expect(page.locator('tbody svg polyline')).toHaveCount(3);

    await toggle.click();

    await expect(page.locator('tbody tr')).toHaveCount(3);
  });

  test('omits the trend line when a test has a single run', async ({ page }) => {
    await open(page);

    await page.getByRole('button', { name: /^beta\b/ }).click();

    const one = page.locator('tbody tr', { hasText: /^one/ });
    await expect(await cellIn(page, one, 'model-b')).toHaveText('87 / 75 ✓');
    await expect((await cellIn(page, one, 'model-b')).locator('svg')).toHaveCount(0);
    await expect((await cellIn(page, one, 'model-a')).locator('svg')).toHaveCount(1);
  });
});

test.describe('Benchmarks view controls', () => {
  test('sorts models by name and keeps the choice in the URL', async ({ page }) => {
    await open(page);

    await page.getByRole('button', { name: 'By name' }).click();

    await expect(headerRow(page).locator('th')).toHaveText([
      'Skill',
      'All models',
      'model-a',
      'model-b',
    ]);
    await expect(page).toHaveURL(/sort=name/);
  });

  test('switches to the 60-day average and re-ranks models by it', async ({ page }) => {
    await open(page);

    await page.getByRole('button', { name: '60-day average' }).click();

    await expect(page).toHaveURL(/metric=history/);
    await expect(headerRow(page).locator('th')).toHaveText([
      'Skill',
      'All models',
      'model-a',
      'model-b',
    ]);
    const modelA = await cellIn(page, overallRow(page), 'model-a');
    await expect(modelA).toContainText('92');
    await expect(modelA).toContainText('18/20 runs passed');
    const cell = await cellIn(page, skillRow(page, 'alpha'), 'model-a');
    await expect(cell).toContainText('84');
    await expect(cell).toContainText('thr 80 · 5/6 runs');
    await expect(page.getByText('average meets threshold')).toBeVisible();
  });

  test('colours history cells by whether the average meets the threshold', async ({ page }) => {
    await page.emulateMedia({ colorScheme: 'light' });
    await open(page, '?metric=history');

    await expect(await cellIn(page, skillRow(page, 'alpha'), 'model-a')).toHaveCSS(
      'background-color',
      'rgb(230, 244, 234)',
    );
    await expect(await cellIn(page, skillRow(page, 'beta'), 'model-a')).toHaveCSS(
      'background-color',
      'rgb(253, 232, 232)',
    );
  });

  test('shows history per test when expanded', async ({ page }) => {
    await open(page, '?metric=history');

    await page.getByRole('button', { name: /^alpha\b/ }).click();

    const one = page.locator('tbody tr', { hasText: /^one/ });
    await expect(await cellIn(page, one, 'model-a')).toHaveText('avg 90 · 5/6 runs');
  });

  test('compact hides the detail lines, deltas and trend lines', async ({ page }) => {
    await open(page);
    await page.getByRole('button', { name: /^alpha\b/ }).click();
    await expect(page.locator('tbody svg')).toHaveCount(3);

    await page.getByLabel('Compact').click();

    await expect(page.getByLabel('Compact')).toBeChecked();
    await expect(page).toHaveURL(/compact=1/);
    await expect(page.getByText('thr 80')).toHaveCount(0);
    await expect(page.getByText('▲6')).toHaveCount(0);
    await expect(page.locator('tbody svg')).toHaveCount(0);
    const one = page.locator('tbody tr', { hasText: /^one/ });
    await expect(await cellIn(page, one, 'model-a')).toHaveText('92 ✓');
  });

  test('lets the user show a subset of models and restore all of them', async ({ page }) => {
    await open(page);
    await page.getByText(/^Models \(/).click();

    await page.getByRole('button', { name: 'model-b', exact: true }).click();

    await expect(headerRow(page).locator('th')).toHaveText(['Skill', 'All models', 'model-a']);
    await expect(page).toHaveURL(/models=model-a/);
    await expect(page.getByText('Models (1 of 2)')).toBeVisible();

    await page.getByRole('button', { name: 'All', exact: true }).click();

    await expect(headerRow(page).locator('th')).toHaveText([
      'Skill',
      'All models',
      'model-b',
      'model-a',
    ]);
    await expect(page).not.toHaveURL(/models=/);
  });

  test('never lets the last visible model be removed', async ({ page }) => {
    await open(page, '?models=model-a');
    await page.getByText(/^Models \(/).click();

    await page.getByRole('button', { name: 'model-a', exact: true }).click();

    await expect(headerRow(page).locator('th')).toHaveText(['Skill', 'All models', 'model-a']);
  });

  test('keeps overall figures independent of which models are shown', async ({ page }) => {
    await open(page, '?models=model-a');

    await expect(await cellIn(page, overallRow(page), 'model-a')).toContainText('3/4 passed · 4/5 tests');
  });

  test('restores the whole view from the URL', async ({ page }) => {
    await open(page, '?metric=history&compact=1&sort=name&models=model-b');

    await expect(page.getByRole('button', { name: '60-day average' })).toHaveAttribute('aria-pressed', 'true');
    await expect(page.getByRole('button', { name: 'By name' })).toHaveAttribute('aria-pressed', 'true');
    await expect(page.getByLabel('Compact')).toBeChecked();
    await expect(headerRow(page).locator('th')).toHaveText(['Skill', 'All models', 'model-b']);
  });

  test('ignores unknown models in the URL', async ({ page }) => {
    await open(page, '?models=nope');

    await expect(headerRow(page).locator('th')).toHaveText([
      'Skill',
      'All models',
      'model-b',
      'model-a',
    ]);
  });
});

test.describe('Benchmarks page states', () => {
  test('shows the empty state when there are no results', async ({ page }) => {
    await mockCatalog(page);
    await mockBenchmarks(page, { models: [], skills: [], summary: {}, test_count: 0 });
    await page.goto('/benchmarks');

    await expect(page.getByText('No results in the last 60 days.')).toBeVisible();
    await expect(page.locator('table')).toHaveCount(0);
  });

  test('shows the outage banner instead of the empty state when the store failed', async ({ page }) => {
    await mockCatalog(page);
    await mockBenchmarks(page, {
      models: [],
      skills: [],
      summary: {},
      test_count: 0,
      error: 'Benchmark results are temporarily unavailable. Try again in a minute.',
    });
    await page.goto('/benchmarks');

    await expect(page.getByRole('status')).toContainText('temporarily unavailable');
    await expect(page.getByText('No results in the last')).toHaveCount(0);
  });

  test('asks the user to sign in when the API answers 401', async ({ page }) => {
    await mockCatalog(page);
    await mockBenchmarks(page, { error: 'identity header required' } as never, 401);
    await page.goto('/benchmarks');

    await expect(page.getByRole('alert')).toHaveText(
      'Sign in to view benchmark results.',
    );
  });

  test('does not call the API when benchmarks are disabled', async ({ page }) => {
    let calls = 0;
    await mockCatalog(page, { benchmarks_enabled: false });
    await page.route('**/api/benchmarks', (route) => {
      calls += 1;
      return route.fulfill({ status: 200, body: '{}' });
    });
    await page.goto('/benchmarks');

    await expect(
      page.getByText('Benchmarks are not enabled on this server.'),
    ).toBeVisible();
    expect(calls).toBe(0);
  });
});
