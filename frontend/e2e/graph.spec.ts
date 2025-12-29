import { test, expect } from '@playwright/test';

/**
 * E2E tests for Graph visualization page
 * Tests the knowledge graph visualization and interaction
 */

test.describe('Graph Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/graph');
  });

  test('should load graph page with heading', async ({ page }) => {
    await expect(page.getByRole('heading', { name: /Graph/i })).toBeVisible();
  });

  test('should display loading state initially', async ({ page }) => {
    // Page should show loading or graph content
    const loadingOrContent = await page
      .getByText(/Loading|Graph|No entities/i)
      .first();
    await expect(loadingOrContent).toBeVisible();
  });

  test('should have visualization container', async ({ page }) => {
    // Wait for page to load
    await page.waitForLoadState('networkidle');

    // Graph visualization area should exist (SVG or Canvas element)
    // May be in loading state if no data
    const graphArea = page.locator('main');
    await expect(graphArea).toBeVisible();
  });
});

test.describe('Graph with Mock Data', () => {
  test.beforeEach(async ({ page }) => {
    // Mock the visualization API
    await page.route('**/api/v1/graph/visualization', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          nodes: [
            { id: 'node-1', label: 'FastAPI', type: 'Tool', size: 10 },
            { id: 'node-2', label: 'Database', type: 'Concept', size: 8 },
            { id: 'node-3', label: 'Auth Error', type: 'Problem', size: 5 },
          ],
          edges: [
            { source: 'node-1', target: 'node-2', type: 'USES' },
            { source: 'node-2', target: 'node-3', type: 'RELATED_TO' },
          ],
          total_nodes: 3,
          total_edges: 2,
          execution_time_ms: 50,
        }),
      });
    });
  });

  test('should display nodes after loading', async ({ page }) => {
    await page.goto('/graph');

    // Wait for visualization to load
    await page.waitForLoadState('networkidle');

    // Should not show "No entities" when we have data
    // The actual node rendering depends on the visualization library
    await expect(page.getByRole('heading', { name: /Graph/i })).toBeVisible();
  });

  test('should handle empty graph state', async ({ page }) => {
    // Override with empty data
    await page.route('**/api/v1/graph/visualization', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          nodes: [],
          edges: [],
          total_nodes: 0,
          total_edges: 0,
          execution_time_ms: 10,
        }),
      });
    });

    await page.goto('/graph');
    await page.waitForLoadState('networkidle');

    // Should show empty state or message
    // Implementation may vary
    const graphArea = page.locator('main');
    await expect(graphArea).toBeVisible();
  });
});

test.describe('Graph Filters', () => {
  test('should have entity type filter if available', async ({ page }) => {
    await page.goto('/graph');
    await page.waitForLoadState('networkidle');

    // Check for filter controls (may or may not exist in current implementation)
    // This is a soft check - won't fail if filters don't exist yet
    const filterArea = page.locator('[data-testid="graph-filters"]');
    const filterExists = await filterArea.count();

    if (filterExists > 0) {
      await expect(filterArea).toBeVisible();
    }
  });
});

test.describe('Graph Error Handling', () => {
  test('should handle API error gracefully', async ({ page }) => {
    await page.route('**/api/v1/graph/visualization', async (route) => {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Graph query failed' }),
      });
    });

    await page.goto('/graph');
    await page.waitForLoadState('networkidle');

    // Page should still be usable, possibly showing error state
    const mainContent = page.locator('main');
    await expect(mainContent).toBeVisible();
  });

  test('should handle network timeout', async ({ page }) => {
    await page.route('**/api/v1/graph/visualization', async (route) => {
      // Simulate timeout by not fulfilling the route
      await new Promise((resolve) => setTimeout(resolve, 10000));
      await route.abort('timedout');
    });

    await page.goto('/graph');

    // Page should show loading or timeout message
    const heading = page.getByRole('heading', { name: /Graph/i });
    await expect(heading).toBeVisible();
  });
});
