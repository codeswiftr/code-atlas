import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import SessionsPage from '@/pages/Sessions';
import { apiClient } from '@/api/client';
import * as router from 'react-router-dom';

// Mock API client
vi.mock('@/api/client', () => ({
  apiClient: {
    discoverSessions: vi.fn(),
    processSessions: vi.fn(),
    listJobs: vi.fn(),
  },
}));

// Mock router
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => vi.fn(),
  };
});

const createTestQueryClient = () => new QueryClient({
  defaultOptions: {
    queries: { retry: false },
    mutations: { retry: false },
  },
});

const renderWithQueryClient = (component: React.ReactElement) => {
  const queryClient = createTestQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      {component}
    </QueryClientProvider>
  );
};

describe('SessionsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('page rendering', () => {
    it('should render sessions page without errors', () => {
      renderWithQueryClient(<SessionsPage />);
      
      expect(screen.getByText('Sessions')).toBeInTheDocument();
      expect(screen.getByText('Discover and process Claude Code session files')).toBeInTheDocument();
    });

    it('should show loading state initially', () => {
      (apiClient.discoverSessions as any).mockReturnValue(new Promise(() => {}));
      
      renderWithQueryClient(<SessionsPage />);
      
      expect(screen.getByText('Discovering sessions...')).toBeInTheDocument();
    });

    it('should show no sessions message when empty', async () => {
      (apiClient.discoverSessions as any).mockResolvedValue({
        sessions: [],
        total_found: 0,
        search_path: '/test',
        message: 'Found 0 sessions'
      });

      renderWithQueryClient(<SessionsPage />);

      await waitFor(() => {
        expect(screen.getByText('No sessions found')).toBeInTheDocument();
      });
    });
  });

  describe('session discovery', () => {
    it('should call discoverSessions API on mount', async () => {
      const mockDiscover = vi.mocked(apiClient.discoverSessions);
      mockDiscover.mockResolvedValue({
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

      renderWithQueryClient(<SessionsPage />);

      await waitFor(() => {
        expect(mockDiscover).toHaveBeenCalledWith({
          limit: 100,
          project_filter: undefined,
        });
      });
    });

    it('should display discovered sessions', async () => {
      (apiClient.discoverSessions as any).mockResolvedValue({
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
            filename: 'section2.jsonl',
            size_bytes: 2048,
            modified_at: '2025-01-02T00:00:00Z',
            project_name: 'another-project'
          }
        ],
        total_found: 2,
        search_path: '/test',
        message: 'Found 2 sessions'
      });

      renderWithQueryClient(<SessionsPage />);

      await waitFor(() => {
        expect(screen.getByText('session1.jsonl')).toBeInTheDocument();
        expect(screen.getByText('session2.jsonl')).toBeInTheDocument();
        expect(screen.getByText('test-project')).toBeInTheDocument();
        expect(screen.getByText('another-project')).toBeInTheDocument();
        expect(screen.getByText('1.0 KB')).toBeInTheDocument();
        expect(screen.getByText('2.0 KB')).toBeInTheDocument();
      });
    });
  });

  describe('session selection', () => {
    it('should allow selecting sessions', async () => {
      (apiClient.discoverSessions as any).mockResolvedValue({
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

      renderWithQueryClient(<SessionsPage />);

      await waitFor(() => {
        const checkbox = screen.getByRole('checkbox');
        expect(checkbox).toBeInTheDocument();
      });

      const checkbox = screen.getByRole('checkbox');
      fireEvent.click(checkbox);

      expect(checkbox).toBeChecked();
      expect(screen.getByText('Process 1 Sessions')).toBeInTheDocument();
    });

    it('should handle select all functionality', async () => {
      (apiClient.discoverSessions as any).mockResolvedValue({
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

      renderWithQueryClient(<SessionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Select All')).toBeInTheDocument();
      });

      const selectAllCheckbox = screen.getByLabelText('Select All');
      fireEvent.click(selectAllCheckbox);

      const checkboxes = screen.getAllByRole('checkbox');
      expect(checkboxes[1]).toBeChecked(); // First checkbox is "Select All"
      expect(checkboxes[2]).toBeChecked();
      expect(screen.getByText('Process 2 Sessions')).toBeInTheDocument();
    });
  });

  describe('session processing', () => {
    it('should call processSessions when process button clicked', async () => {
      const mockDiscover = vi.mocked(apiClient.discoverSessions);
      const mockProcess = vi.mocked(apiClient.processSessions);
      
      mockDiscover.mockResolvedValue({
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

      mockProcess.mockResolvedValue({
        job: {
          job_id: 'test-job-id',
          status: 'pending',
          total_sessions: 1,
          processed_sessions: 0,
          failed_sessions: 0
        },
        message: 'Processing job created'
      });

      renderWithQueryClient(<SessionsPage />);

      await waitFor(() => {
        const checkbox = screen.getByRole('checkbox');
        fireEvent.click(checkbox);
      });

      const processButton = screen.getByText('Process 1 Sessions');
      fireEvent.click(processButton);

      await waitFor(() => {
        expect(mockProcess).toHaveBeenCalledWith({
          session_paths: ['/test/session1.jsonl'],
          use_llm: true,
          dry_run: false,
          max_cost_per_session: 0.02
        });
      });
    });

    it('should disable process button when no sessions selected', async () => {
      (apiClient.discoverSessions as any).mockResolvedValue({
        sessions: [],
        total_found: 0,
        search_path: '/test',
        message: 'Found 0 sessions'
      });

      renderWithQueryClient(<SessionsPage />);

      await waitFor(() => {
        const processButton = screen.getByText('Process 0 Sessions');
        expect(processButton).toBeDisabled();
      });
    });
  });

  describe('filtering', () => {
    it('should filter sessions by search term', async () => {
      (apiClient.discoverSessions as any).mockResolvedValue({
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

      renderWithQueryClient(<SessionsPage />);

      await waitFor(() => {
        expect(screen.getByText('auth-session.jsonl')).toBeInTheDocument();
        expect(screen.getByText('database-session.jsonl')).toBeInTheDocument();
      });

      const searchInput = screen.getByPlaceholderText('Search filenames...');
      fireEvent.change(searchInput, { target: { value: 'auth' } });

      await waitFor(() => {
        expect(screen.getByText('auth-session.jsonl')).toBeInTheDocument();
        expect(screen.queryByText('database-session.jsonl')).not.toBeInTheDocument();
      });
    });

    it('should filter sessions by project name', async () => {
      (apiClient.discoverSessions as any).mockResolvedValue({
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

      renderWithQueryClient(<SessionsPage />);

      await waitFor(() => {
        expect(screen.getByText('auth-project')).toBeInTheDocument();
        expect(screen.getByText('database-project')).toBeInTheDocument();
      });

      const projectInput = screen.getByPlaceholderText('Filter by project...');
      fireEvent.change(projectInput, { target: { value: 'auth' } });

      await waitFor(() => {
        expect(screen.getByText('auth-project')).toBeInTheDocument();
        expect(screen.queryByText('database-project')).not.toBeInTheDocument();
      });
    });
  });

  describe('job status display', () => {
    it('should display processing jobs', async () => {
      (apiClient.listJobs as any).mockResolvedValue([
        {
          job_id: 'test-job-1',
          status: 'completed',
          total_sessions: 5,
          processed_sessions: 5,
          failed_sessions: 0,
          created_at: '2025-01-01T00:00:00Z',
          completed_at: '2025-01-01T00:05:00Z'
        },
        {
          job_id: 'test-job-2',
          status: 'running',
          total_sessions: 3,
          processed_sessions: 1,
          failed_sessions: 0,
          current_session: 'session3.jsonl',
          created_at: '2025-01-01T01:00:00Z',
          started_at: '2025-01-01T01:01:00Z'
        }
      ]);

      renderWithQueryClient(<SessionsPage />);

      await waitFor(() => {
        expect(screen.getByText('Processing Jobs')).toBeInTheDocument();
        expect(screen.getByText('test-job-1')).toBeInTheDocument();
        expect(screen.getByText('test-job-2')).toBeInTheDocument();
        expect(screen.getByText('completed')).toBeInTheDocument();
        expect(screen.getByText('running')).toBeInTheDocument();
        expect(screen.getByText('5 / 5 sessions processed')).toBeInTheDocument();
        expect(screen.getByText('1 / 3 sessions processed')).toBeInTheDocument();
        expect(screen.getByText('Current: session3.jsonl')).toBeInTheDocument();
      });
    });
  });
});