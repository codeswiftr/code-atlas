import { test, expect } from '@playwright/test';

/**
 * E2E tests for RAG (Retrieval-Augmented Generation) page
 * Tests the Q&A interface for querying the knowledge graph
 */

test.describe('RAG Page', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/rag');
  });

  test('should load RAG page with heading', async ({ page }) => {
    await expect(page.getByRole('heading', { name: /RAG Query/i })).toBeVisible();
  });

  test('should display question input form', async ({ page }) => {
    // Check for question textarea
    const questionInput = page.locator('#question');
    await expect(questionInput).toBeVisible();

    // Check for entity type filter
    const entityTypeSelect = page.locator('#entity_type');
    await expect(entityTypeSelect).toBeVisible();

    // Check for submit button
    await expect(page.getByRole('button', { name: /Ask Question/i })).toBeVisible();
  });

  test('should have placeholder text in question input', async ({ page }) => {
    const questionInput = page.locator('#question');
    await expect(questionInput).toHaveAttribute(
      'placeholder',
      /What problems keep recurring/i
    );
  });

  test('should disable submit button when question is empty', async ({ page }) => {
    const submitButton = page.getByRole('button', { name: /Ask Question/i });
    await expect(submitButton).toBeDisabled();
  });

  test('should enable submit button when question is entered', async ({ page }) => {
    const questionInput = page.locator('#question');
    await questionInput.fill('What are the most common problems?');

    const submitButton = page.getByRole('button', { name: /Ask Question/i });
    await expect(submitButton).toBeEnabled();
  });

  test('should have entity type filter options', async ({ page }) => {
    const entityTypeSelect = page.locator('#entity_type');

    // Check all options are available
    await expect(entityTypeSelect.locator('option')).toHaveCount(6); // All Types + 5 types
    await expect(entityTypeSelect.locator('option', { hasText: 'All Types' })).toBeVisible();
    await expect(entityTypeSelect.locator('option', { hasText: 'Concept' })).toBeVisible();
    await expect(entityTypeSelect.locator('option', { hasText: 'Problem' })).toBeVisible();
  });
});

test.describe('RAG Query Submission', () => {
  test('should show loading state when submitting', async ({ page }) => {
    // Mock the API to delay response
    await page.route('**/api/v1/insights/rag/query', async (route) => {
      await new Promise((resolve) => setTimeout(resolve, 1000));
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          answer: 'Test answer',
          sources: [],
          confidence: 0.8,
          context_entities: [],
          search_results_count: 0,
          execution_time_ms: 100,
          message: 'Success',
        }),
      });
    });

    await page.goto('/rag');

    // Fill and submit
    await page.locator('#question').fill('What are the common problems?');
    await page.getByRole('button', { name: /Ask Question/i }).click();

    // Should show loading state
    await expect(page.getByText(/Processing/i)).toBeVisible();
  });

  test('should display answer after successful query', async ({ page }) => {
    // Mock successful API response
    await page.route('**/api/v1/insights/rag/query', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          answer: 'Based on the knowledge graph, the most common problem is configuration issues.',
          sources: ['entity-1', 'entity-2'],
          confidence: 0.85,
          context_entities: [
            { entity_id: 'e1', entity_name: 'Config Error', entity_type: 'Problem' },
          ],
          search_results_count: 3,
          execution_time_ms: 150,
          message: 'Success',
        }),
      });
    });

    await page.goto('/rag');

    // Submit question
    await page.locator('#question').fill('What are the common problems?');
    await page.getByRole('button', { name: /Ask Question/i }).click();

    // Wait for and verify answer
    await expect(page.getByText(/configuration issues/i)).toBeVisible();
    await expect(page.getByText(/Confidence: 85%/i)).toBeVisible();
  });

  test('should display sources section when sources exist', async ({ page }) => {
    await page.route('**/api/v1/insights/rag/query', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          answer: 'Test answer with sources',
          sources: ['source-entity-1', 'source-entity-2'],
          confidence: 0.75,
          context_entities: [],
          search_results_count: 2,
          execution_time_ms: 100,
          message: 'Success',
        }),
      });
    });

    await page.goto('/rag');
    await page.locator('#question').fill('Test question');
    await page.getByRole('button', { name: /Ask Question/i }).click();

    // Verify sources section
    await expect(page.getByRole('heading', { name: /Sources/i })).toBeVisible();
    await expect(page.getByText('source-entity-1')).toBeVisible();
    await expect(page.getByText('source-entity-2')).toBeVisible();
  });

  test('should display context entities section', async ({ page }) => {
    await page.route('**/api/v1/insights/rag/query', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          success: true,
          answer: 'Test answer',
          sources: [],
          confidence: 0.8,
          context_entities: [
            { entity_id: 'e1', entity_name: 'FastAPI', entity_type: 'Tool' },
            { entity_id: 'e2', entity_name: 'Database', entity_type: 'Concept' },
          ],
          search_results_count: 2,
          execution_time_ms: 100,
          message: 'Success',
        }),
      });
    });

    await page.goto('/rag');
    await page.locator('#question').fill('Test question');
    await page.getByRole('button', { name: /Ask Question/i }).click();

    // Verify context entities
    await expect(page.getByRole('heading', { name: /Context Entities/i })).toBeVisible();
    await expect(page.getByText('FastAPI')).toBeVisible();
    await expect(page.getByText('Database')).toBeVisible();
  });

  test('should handle API error gracefully', async ({ page }) => {
    await page.route('**/api/v1/insights/rag/query', async (route) => {
      await route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Internal server error' }),
      });
    });

    await page.goto('/rag');
    await page.locator('#question').fill('Test question');
    await page.getByRole('button', { name: /Ask Question/i }).click();

    // Should show error message
    await expect(page.getByText(/Error/i)).toBeVisible();
  });
});
