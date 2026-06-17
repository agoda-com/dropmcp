import { test, expect } from '@playwright/test';
import type { CatalogItem, SkillTelemetryResult } from '../src/api/catalog';

const MOCK_TELEMETRY_RESULTS: SkillTelemetryResult[] = [
  {
    test_name: 'agoda-ioc-dependency-injection/basic-registration',
    passed: false,
    score: 0,
    threshold: 0.8,
    display_score: '0.0%',
    display_threshold: '/80.0%',
    display_duration: '4.5s',
    display_date: 'Apr 21, 4:26 AM UTC',
    reasoning:
      'The agent failed to provide any JavaScript code or a .pptx file as required by the evaluation criteria. It only provided a markdown analysis of the data, completely missing the expected output format.',
    error: null,
    worker_model: 'gemini-3-pro',
    pipeline_id: '12345',
    short_sha: '7e0f936',
  },
  {
    test_name: 'agoda-ioc-dependency-injection/basic-registration',
    passed: true,
    score: 0.95,
    threshold: 0.8,
    display_score: '95.0%',
    display_threshold: '/80.0%',
    display_duration: '12.3s',
    display_date: 'Apr 21, 4:26 AM UTC',
    reasoning:
      'The agent produced a well-structured service with correct attribute-based DI registration and appropriate scoping.',
    error: null,
    worker_model: 'claude-sonnet-4',
    pipeline_id: '12345',
    short_sha: '7e0f936',
  },
  {
    test_name: 'agoda-ioc-dependency-injection/scoped-lifetime',
    passed: true,
    score: 0.88,
    threshold: 0.8,
    display_score: '88.0%',
    display_threshold: '/80.0%',
    display_duration: '8.1s',
    display_date: 'Apr 21, 4:30 AM UTC',
    reasoning: 'Service registration and scoped lifetime met all evaluation criteria.',
    error: null,
    worker_model: 'gemini-3-pro',
    pipeline_id: '12345',
    short_sha: '7e0f936',
  },
];

const SKILL_ITEM: CatalogItem = {
  name: 'agoda-ioc-dependency-injection',
  type: 'skill',
  category: 'csharp',
  description: 'Register and resolve dependencies with Agoda.IoC attribute-based DI.',
  arguments: [],
  has_hero: false,
  has_thumbnail: false,
  screenshot_count: 0,
  example_count: 0,
  thumbnail_url: null,
  hero_url: null,
  screenshots: [],
  examples: [],
};

function mockApis(
  page: import('@playwright/test').Page,
  results: SkillTelemetryResult[] = MOCK_TELEMETRY_RESULTS,
) {
  return Promise.all([
    page.route('**/catalog/skill/agoda-ioc-dependency-injection', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(SKILL_ITEM),
      }),
    ),
    page.route('**/api/telemetry/agoda-ioc-dependency-injection', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          project: 'skills-mcp',
          skill_name: 'agoda-ioc-dependency-injection',
          commit_sha: '7e0f936abc123',
          results,
        }),
      }),
    ),
  ]);
}

test.describe('Telemetry Panel', () => {
  test('groups results by test name', async ({ page }) => {
    await mockApis(page);
    await page.goto('/skill/agoda-ioc-dependency-injection');
    await page.waitForSelector('h2:has-text("E2E Test Results")');

    const groups = page.locator('h3');
    await expect(groups).toHaveCount(2);
    await expect(groups.nth(0)).toHaveText('basic-registration');
    await expect(groups.nth(1)).toHaveText('scoped-lifetime');
  });

  test('shows pass and fail status dots with correct colours', async ({ page }) => {
    await mockApis(page);
    await page.goto('/skill/agoda-ioc-dependency-injection');
    await page.waitForSelector('h2:has-text("E2E Test Results")');

    const panel = page.locator('h2:has-text("E2E Test Results")').locator('..');
    await expect(panel).toHaveScreenshot('telemetry-panel.png');
  });

  test('displays reasoning text without truncation', async ({ page }) => {
    await mockApis(page);
    await page.goto('/skill/agoda-ioc-dependency-injection');
    await page.waitForSelector('h2:has-text("E2E Test Results")');

    const reasoning = page.getByText('The agent failed to provide any JavaScript code');
    await expect(reasoning).toBeVisible();
    await expect(reasoning).toContainText('completely missing the expected output format');
  });

  test('colour codes score green for pass, red for fail', async ({ page }) => {
    await mockApis(page);
    await page.goto('/skill/agoda-ioc-dependency-injection');
    await page.waitForSelector('h2:has-text("E2E Test Results")');

    const failScore = page.getByText('0.0%').first();
    const passScore = page.getByText('95.0%');
    await expect(failScore).toHaveCSS('color', 'rgb(239, 68, 68)');
    await expect(passScore).toHaveCSS('color', 'rgb(22, 163, 74)');
  });

  test('shows empty state when no results', async ({ page }) => {
    await mockApis(page, []);
    await page.goto('/skill/agoda-ioc-dependency-injection');
    await page.waitForSelector('h2:has-text("E2E Test Results")');

    await expect(page.getByText('No E2E test results available yet.')).toBeVisible();
    const panel = page.locator('h2:has-text("E2E Test Results")').locator('..');
    await expect(panel).toHaveScreenshot('telemetry-empty.png');
  });

  test('renders correctly in dark mode', async ({ page }) => {
    await page.emulateMedia({ colorScheme: 'dark' });
    await mockApis(page);
    await page.goto('/skill/agoda-ioc-dependency-injection');
    await page.waitForSelector('h2:has-text("E2E Test Results")');

    const panel = page.locator('h2:has-text("E2E Test Results")').locator('..');
    await expect(panel).toHaveScreenshot('telemetry-panel-dark.png');
  });
});
