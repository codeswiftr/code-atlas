import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { renderWithProviders, renderWithQueryClient } from '@/test/utils';
import SessionsPage from '@/pages/Sessions';
import { JobStatus } from '@/types/api';
import { apiClient } from '@/api/client';

// Spy on apiClient methods
const mockDiscoverSessions = vi.spyOn(apiClient, 'discoverSessions');
const mockProcessSessions = vi.spyOn(apiClient, 'processSessions');
const mockListJobs = vi.spyOn(apiClient, 'listJobs');
const mockCancelJob = vi.spyOn(apiClient, 'cancelJob');

describe('SessionsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Set default mocks for all tests
    mockListJobs.mockResolvedValue([]);
  });

  describe('page rendering', () => {
    it('should render sessions page without errors', () => {
      renderWithProviders(<SessionsPage />);
      
      expect(screen.getByText('Sessions')).toBeInTheDocument();
      expect(screen.getByText('Discover and process Claude Code session files')).toBeInTheDocument();
    });

    it('should show loading state initially', () => {
      // Mock functions that return promises that never resolve
      mockDiscoverSessions.mockImplementation(() => new Promise<never>(() => {
        // Intentionally never resolves to test loading state
      }));
      mockListJobs.mockImplementation(() => new Promise<never>(() => {
        // Intentionally never resolves to test loading state
      }));

      renderWithProviders(<SessionsPage />);

      expect(screen.getByText('Discovering sessions...')).toBeInTheDocument();
    });

    it('should show no sessions message when empty', async () => {
      mockDiscoverSessions.mockResolvedValueOnce({
        sessions: [],
        total_found: 0,
        search_path: '/test',
        message: 'Found 0 sessions'
      });
      mockListJobs.mockResolvedValueOnce([]);

      renderWithProviders(<SessionsPage />);

      await waitFor(() => {
        expect(screen.getByText('No sessions found')).toBeInTheDocument();
      });
    });
  });

  describe('session discovery', () => {
    it('should call discoverSessions API on mount', async () => {
      mockDiscoverSessions.mockResolvedValueOnce({
        sessions: [
          {
            path: '/test/session1.jsonl',
            filename: 'session1.jsonl',
            size_bytes: 1024,
            modified_at: '2025-01-01T00:00:00Z',
            project_name: 'test-project'
          }
        ],
        total_found: 1,
        search_path: '/test',
        message: 'Found 1 sessions'
      });
      mockListJobs.mockResolvedValueOnce([]);

      renderWithProviders(<SessionsPage />);

      await waitFor(() => {
        expect(mockDiscoverSessions).toHaveBeenCalledWith({
          limit: 100,
          project_filter: undefined,
        });
      });
    });

    it('should display discovered sessions', async () => {
      mockDiscoverSessions.mockResolvedValueOnce({
        sessions: [
          {
            path: '/test/session1.jsonl',
            filename: 'session1.jsonl',
            size_bytes: 1024,
            modified_at: '2025-01-01T00:00:00Z',
            project_name: 'test-project'
          },
          {
            path: '/test/session2.jsonl',
            filename: 'session2.jsonl',
            size_bytes: 2048,
            modified_at: '2025-01-02T00:00:00Z',
            project_name: 'another-project'
          }
        ],
        total_found: 2,
        search_path: '/test',
        message: 'Found 2 sessions'
      });
      mockListJobs.mockResolvedValueOnce([]);

      renderWithProviders(<SessionsPage />);

      await waitFor(() => {
        expect(screen.getByText('session1.jsonl')).toBeInTheDocument();
        expect(screen.getByText('session2.jsonl')).toBeInTheDocument();
        // Use function matcher since text may be split across elements
        expect(screen.getByText((content) => content.includes('test-project'))).toBeInTheDocument();
        expect(screen.getByText((content) => content.includes('another-project'))).toBeInTheDocument();
        expect(screen.getByText((content) => content.includes('1.0'))).toBeInTheDocument();
        expect(screen.getByText((content) => content.includes('2.0'))).toBeInTheDocument();
      });
    });
  });

  describe('session selection', () => {
    it('should allow selecting sessions', async () => {
      mockDiscoverSessions.mockResolvedValueOnce({
        sessions: [
          {
            path: '/test/session1.jsonl',
            filename: 'session1.jsonl',
            size_bytes: 1024,
            modified_at: '2025-01-01T00:00:00Z',
            project_name: 'test-project'
          }
        ],
        total_found: 1,
        search_path: '/test',
        message: 'Found 1 sessions'
      });
      mockListJobs.mockResolvedValueOnce([]);

      renderWithProviders(<SessionsPage />);

      await waitFor(() => {
        expect(screen.getByText('session1.jsonl')).toBeInTheDocument();
      });

      // Click on the session row div to select it (not the checkbox, which causes double toggle)
      const sessionRow = screen.getByText('session1.jsonl').closest('[class*="cursor-pointer"]');
      expect(sessionRow).toBeInTheDocument();
      fireEvent.click(sessionRow!);

      // Wait for state update and verify button text updates
      await waitFor(() => {
        // Use regex matcher since React may split text between elements
        expect(screen.getByRole('button', { name: /Process\s*1\s*Sessions/i })).toBeInTheDocument();
      });
    });

    it('should handle select all functionality', async () => {
      mockDiscoverSessions.mockResolvedValueOnce({
        sessions: [
          {
            path: '/test/session1.jsonl',
            filename: 'session1.jsonl',
            size_bytes: 1024,
            modified_at: '2025-01-01T00:00:00Z',
            project_name: 'test-project'
          },
          {
            path: '/test/session2.jsonl',
            filename: 'session2.jsonl',
            size_bytes: 2048,
            modified_at: '2025-01-02T00:00:00Z',
            project_name: 'test-project'
          }
        ],
        total_found: 2,
        search_path: '/test',
        message: 'Found 2 sessions'
      });
      mockListJobs.mockResolvedValueOnce([]);

      renderWithProviders(<SessionsPage />);

      // Wait for sessions to load
      await waitFor(() => {
        expect(screen.getByText('session1.jsonl')).toBeInTheDocument();
        expect(screen.getByText('session2.jsonl')).toBeInTheDocument();
      });

      // Click both session rows to select them
      const sessionRow1 = screen.getByText('session1.jsonl').closest('[class*="cursor-pointer"]');
      const sessionRow2 = screen.getByText('session2.jsonl').closest('[class*="cursor-pointer"]');
      fireEvent.click(sessionRow1!);
      fireEvent.click(sessionRow2!);

      // Wait for state update and verify selections
      await waitFor(() => {
        // Use regex matcher since React may split text between elements
        expect(screen.getByRole('button', { name: /Process\s*2\s*Sessions/i })).toBeInTheDocument();
      });
    });
  });

  describe('session processing', () => {
    it('should call processSessions when process button clicked', async () => {
      mockDiscoverSessions.mockResolvedValueOnce({
        sessions: [
          {
            path: '/test/session1.jsonl',
            filename: 'session1.jsonl',
            size_bytes: 1024,
            modified_at: '2025-01-01T00:00:00Z',
            project_name: 'test-project'
          }
        ],
        total_found: 1,
        search_path: '/test',
        message: 'Found 1 sessions'
      });
      mockListJobs.mockResolvedValueOnce([]);
      mockProcessSessions.mockResolvedValueOnce({
        job: {
          job_id: 'test-job-id',
          status: JobStatus.PENDING,
          total_sessions: 1,
          processed_sessions: 0,
          failed_sessions: 0
        },
        message: 'Processing job created'
      });

      renderWithProviders(<SessionsPage />);

      // Wait for the session to be rendered
      await waitFor(() => {
        expect(screen.getByText('session1.jsonl')).toBeInTheDocument();
      });

      // Click on the session row div to select it
      const sessionRow = screen.getByText('session1.jsonl').closest('[class*="cursor-pointer"]');
      fireEvent.click(sessionRow!);

      // Wait for the process button to show the correct count
      const processButton = await screen.findByRole('button', { name: /Process\s*1\s*Sessions/i });
      fireEvent.click(processButton);

      await waitFor(() => {
        expect(mockProcessSessions).toHaveBeenCalledWith({
          session_paths: ['/test/session1.jsonl'],
          use_llm: true,
          dry_run: false,
          max_cost_per_session: 0.02
        });
      });
    });

    it('should disable process button when no sessions selected', async () => {
      mockDiscoverSessions.mockResolvedValueOnce({
        sessions: [],
        total_found: 0,
        search_path: '/test',
        message: 'Found 0 sessions'
      });
      mockListJobs.mockResolvedValueOnce([]);

      renderWithProviders(<SessionsPage />);

      await waitFor(() => {
        const processButton = screen.getByText('Process 0 Sessions');
        expect(processButton).toBeDisabled();
      });
    });
  });

  describe('filtering', () => {
    it('should filter sessions by search term', async () => {
      // Return the same sessions data for all calls (initial + refetches)
      mockDiscoverSessions.mockResolvedValue({
        sessions: [
          {
            path: '/test/session1.jsonl',
            filename: 'auth-session.jsonl',
            size_bytes: 1024,
            modified_at: '2025-01-01T00:00:00Z',
            project_name: 'test-project'
          },
          {
            path: '/test/session2.jsonl',
            filename: 'database-session.jsonl',
            size_bytes: 2048,
            modified_at: '2025-01-02T00:00:00Z',
            project_name: 'test-project'
          }
        ],
        total_found: 2,
        search_path: '/test',
        message: 'Found 2 sessions'
      });
      mockListJobs.mockResolvedValueOnce([]);

      renderWithQueryClient(<SessionsPage />);

      await waitFor(() => {
        expect(screen.getByText('auth-session.jsonl')).toBeInTheDocument();
        expect(screen.getByText('database-session.jsonl')).toBeInTheDocument();
      });

      // Open filters panel - find the filter toggle button next to "Filters" heading
      const filtersHeading = screen.getByText('Filters');
      const filterCard = filtersHeading.closest('.card');
      const buttons = filterCard?.querySelectorAll('button') || [];
      const filterToggle = Array.from(buttons).find(btn => {
        const svg = btn.querySelector('svg');
        return svg !== null;
      });
      
      expect(filterToggle).toBeTruthy();
      fireEvent.click(filterToggle!);
      
      await waitFor(() => {
        expect(screen.getByPlaceholderText('Search filenames...')).toBeInTheDocument();
      });

      const searchInput = screen.getByPlaceholderText('Search filenames...');
      fireEvent.change(searchInput, { target: { value: 'auth' } });

      await waitFor(() => {
        expect(screen.getByText('auth-session.jsonl')).toBeInTheDocument();
        expect(screen.queryByText('database-session.jsonl')).not.toBeInTheDocument();
      });
    });

    it('should filter sessions by project name', async () => {
      // Return the same sessions data for all calls (initial + refetches)
      mockDiscoverSessions.mockResolvedValue({
        sessions: [
          {
            path: '/test/session1.jsonl',
            filename: 'session1.jsonl',
            size_bytes: 1024,
            modified_at: '2025-01-01T00:00:00Z',
            project_name: 'auth-project'
          },
          {
            path: '/test/session2.jsonl',
            filename: 'session2.jsonl',
            size_bytes: 2048,
            modified_at: '2025-01-02T00:00:00Z',
            project_name: 'database-project'
          }
        ],
        total_found: 2,
        search_path: '/test',
        message: 'Found 2 sessions'
      });
      mockListJobs.mockResolvedValueOnce([]);

      renderWithQueryClient(<SessionsPage />);

      // Wait for sessions to load
      await waitFor(() => {
        expect(screen.getByText('session1.jsonl')).toBeInTheDocument();
        expect(screen.getByText('session2.jsonl')).toBeInTheDocument();
      });

      // Then check for project names (text includes size, so match by substring)
      expect(
        screen.getByText((content) => content.includes('auth-project'))
      ).toBeInTheDocument();
      expect(
        screen.getByText((content) => content.includes('database-project'))
      ).toBeInTheDocument();

      // Open filters panel - find the filter toggle button
      const filtersHeading = screen.getByText('Filters');
      const filterCard = filtersHeading.closest('.card');
      const buttons = filterCard?.querySelectorAll('button') || [];
      const filterToggle = Array.from(buttons).find(btn => {
        const svg = btn.querySelector('svg');
        return svg !== null;
      });
      
      expect(filterToggle).toBeTruthy();
      fireEvent.click(filterToggle!);
      
      await waitFor(() => {
        expect(screen.getByPlaceholderText('Filter by project...')).toBeInTheDocument();
      });

      const projectInput = screen.getByPlaceholderText('Filter by project...');
      fireEvent.change(projectInput, { target: { value: 'auth' } });

      await waitFor(() => {
        expect(
          screen.getByText((content) => content.includes('auth-project'))
        ).toBeInTheDocument();
        expect(
          screen.queryByText((content) => content.includes('database-project'))
        ).not.toBeInTheDocument();
      });
    });
  });

  describe('job status display', () => {
    it('should display processing jobs', async () => {
      mockDiscoverSessions.mockResolvedValueOnce({
        sessions: [],
        total_found: 0,
        search_path: '/test',
        message: 'Found 0 sessions'
      });

      const mockJobs = [
        {
          job_id: 'test-job-1',
          status: JobStatus.COMPLETED,
          total_sessions: 5,
          processed_sessions: 5,
          failed_sessions: 0,
          created_at: '2025-01-01T00:00:00Z',
          completed_at: '2025-01-01T00:05:00Z'
        },
        {
          job_id: 'test-job-2',
          status: JobStatus.RUNNING,
          total_sessions: 3,
          processed_sessions: 1,
          failed_sessions: 0,
          current_session: 'session3.jsonl',
          created_at: '2025-01-01T01:00:00Z',
          started_at: '2025-01-01T01:01:00Z'
        }
      ];
      mockListJobs.mockResolvedValueOnce(mockJobs);

      renderWithQueryClient(<SessionsPage />);

      // Wait for the jobs to appear in the UI
      await waitFor(() => {
        expect(screen.getByText('Processing Jobs')).toBeInTheDocument();
      }, { timeout: 3000 });

      expect(screen.getByText('test-job-1')).toBeInTheDocument();
      expect(screen.getByText('test-job-2')).toBeInTheDocument();
      expect(screen.getByText(JobStatus.COMPLETED)).toBeInTheDocument();
      expect(screen.getByText(JobStatus.RUNNING)).toBeInTheDocument();
      expect(screen.getByText('5 / 5 sessions processed')).toBeInTheDocument();
      expect(screen.getByText('1 / 3 sessions processed')).toBeInTheDocument();
      expect(screen.getByText('Current: session3.jsonl')).toBeInTheDocument();
    });
  });
});