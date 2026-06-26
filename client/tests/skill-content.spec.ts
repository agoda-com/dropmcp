import { test, expect } from '@playwright/test';
import type { CatalogItem } from '../src/api/catalog';

const SKILL_WITH_CONTENT: CatalogItem = {
  name: 'hello-world',
  type: 'skill',
  category: 'examples',
  description: 'A minimal example skill for testing the catalog UI.',
  arguments: [],
  has_hero: false,
  has_thumbnail: false,
  screenshot_count: 0,
  example_count: 0,
  thumbnail_url: null,
  hero_url: null,
  screenshots: [],
  examples: [],
  content_markdown: '## Hello\n\nUse this skill for testing.\n\n```python\nprint("hi")\n```',
  resources: [
    {
      path: 'scripts/run.py',
      name: 'run.py',
      url: '/catalog/skill/hello-world/resource/scripts/run.py',
      mime_type: 'text/x-python',
    },
  ],
};

const RESOURCE_BODY = 'def run():\n    print("hi")\n';

function mockSkillDetail(page: import('@playwright/test').Page) {
  return Promise.all([
    page.route('**/catalog/skill/hello-world', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(SKILL_WITH_CONTENT),
      }),
    ),
    page.route('**/catalog/skill/hello-world/resource/scripts/run.py', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'text/plain',
        body: RESOURCE_BODY,
      }),
    ),
    page.route('**/api/telemetry/hello-world', (route) =>
      route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          project: 'test',
          skill_name: 'hello-world',
          results: [],
        }),
      }),
    ),
  ]);
}

test.describe('Skill content', () => {
  test('renders instructions before E2E test results', async ({ page }) => {
    await mockSkillDetail(page);
    await page.goto('/skill/hello-world');
    await page.waitForSelector('h2:has-text("Instructions")');

    const instructions = page.locator('h2:has-text("Instructions")');
    const telemetry = page.locator('h2:has-text("E2E Test Results")');
    const instructionsBox = await instructions.boundingBox();
    const telemetryBox = await telemetry.boundingBox();
    expect(instructionsBox).not.toBeNull();
    expect(telemetryBox).not.toBeNull();
    expect(instructionsBox!.y).toBeLessThan(telemetryBox!.y);
  });

  test('highlights fenced code in instructions', async ({ page }) => {
    await mockSkillDetail(page);
    await page.goto('/skill/hello-world');
    await page.waitForSelector('code.hljs');

    await expect(page.locator('code.hljs')).toContainText('print("hi")');
  });

  test('opens resource modal with highlighted code', async ({ page }) => {
    await mockSkillDetail(page);
    await page.goto('/skill/hello-world');
    await page.getByRole('button', { name: 'scripts/run.py' }).click();

    await expect(page.getByRole('dialog')).toBeVisible();
    await expect(page.getByRole('dialog')).toContainText('def run()');
    await expect(page.locator('[role="dialog"] code.hljs')).toContainText('print("hi")');
  });

  test('closes resource modal on Escape and overlay click', async ({ page }) => {
    await mockSkillDetail(page);
    await page.goto('/skill/hello-world');
    await page.getByRole('button', { name: 'scripts/run.py' }).click();
    await expect(page.getByRole('dialog')).toBeVisible();

    await page.keyboard.press('Escape');
    await expect(page.getByRole('dialog')).toHaveCount(0);

    await page.getByRole('button', { name: 'scripts/run.py' }).click();
    await page.locator('[role="presentation"]').click({ position: { x: 5, y: 5 } });
    await expect(page.getByRole('dialog')).toHaveCount(0);
  });
});
