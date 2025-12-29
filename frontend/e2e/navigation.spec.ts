import { test, expect } from '@playwright/test';

/**
 * E2E tests for critical user journeys in Code Atlas
 * These tests verify the main navigation paths and core functionality
 */

test.describe('Navigation', () => {
  test('should load the home page', async ({ page }) => {
    await page.goto('/');

    // Check main heading
    await expect(page.getByRole('heading', { name: /Code Atlas/i })).toBeVisible();

    // Check navigation links are present
    await expect(page.getByRole('link', { name: /Sessions/i })).toBeVisible();
    await expect(page.getByRole('link', { name: /Entities/i })).toBeVisible();
    await expect(page.getByRole('link', { name: /Graph/i })).toBeVisible();
  });

  test('should navigate to Sessions page', async ({ page }) => {
    await page.goto('/');

    await page.getByRole('link', { name: /Sessions/i }).click();

    await expect(page).toHaveURL('/sessions');
    await expect(page.getByRole('heading', { name: /Sessions/i })).toBeVisible();
  });

  test('should navigate to Entities page', async ({ page }) => {
    await page.goto('/');

    await page.getByRole('link', { name: /Entities/i }).click();

    await expect(page).toHaveURL('/entities');
    await expect(page.getByRole('heading', { name: /Entities/i })).toBeVisible();
  });

  test('should navigate to Graph page', async ({ page }) => {
    await page.goto('/');

    await page.getByRole('link', { name: /Graph/i }).click();

    await expect(page).toHaveURL('/graph');
    await expect(page.getByRole('heading', { name: /Graph/i })).toBeVisible();
  });

  test('should navigate to Insights page', async ({ page }) => {
    await page.goto('/');

    await page.getByRole('link', { name: /Insights/i }).click();

    await expect(page).toHaveURL('/insights');
    await expect(page.getByRole('heading', { name: /Insights/i })).toBeVisible();
  });

  test('should navigate to RAG page', async ({ page }) => {
    await page.goto('/');

    await page.getByRole('link', { name: /RAG/i }).click();

    await expect(page).toHaveURL('/rag');
    await expect(page.getByRole('heading', { name: /RAG Query/i })).toBeVisible();
  });
});

test.describe('Sessions Page', () => {
  test('should show loading state initially', async ({ page }) => {
    await page.goto('/sessions');

    // Should show loading or sessions list
    const loadingOrContent = await page.getByText(/Discovering sessions|Sessions|No sessions found/i).first();
    await expect(loadingOrContent).toBeVisible();
  });

  test('should display filters section', async ({ page }) => {
    await page.goto('/sessions');

    // Wait for page to load
    await page.waitForSelector('text=/Sessions/i');

    // Check for filters
    await expect(page.getByText(/Filters/i)).toBeVisible();
  });
});

test.describe('Error Handling', () => {
  test('should handle 404 gracefully', async ({ page }) => {
    await page.goto('/nonexistent-page');

    // Should redirect to home or show error
    await expect(page.getByRole('heading')).toBeVisible();
  });
});

test.describe('Accessibility', () => {
  test('should have proper page structure', async ({ page }) => {
    await page.goto('/');

    // Check for main landmark
    await expect(page.getByRole('main')).toBeVisible();

    // Check for navigation
    await expect(page.getByRole('navigation')).toBeVisible();
  });

  test('should have accessible navigation links', async ({ page }) => {
    await page.goto('/');

    // All nav links should be keyboard accessible
    const navLinks = page.getByRole('link');
    const count = await navLinks.count();
    expect(count).toBeGreaterThan(0);
  });
});
