import { describe, it, expect, vi, beforeEach } from 'vitest';
import { CodeAtlasAPIClient } from '@/api/client';

// Mock fetch
global.fetch = vi.fn();

describe('CodeAtlasAPIClient', () => {
  let client: CodeAtlasAPIClient;

  beforeEach(() => {
    vi.clearAllMocks();
    client = new CodeAtlasAPIClient('http://test-api', 'test-api-key');
  });

  describe('initialization', () => {
    it('should initialize with base URL and API key', () => {
      expect(client).toBeDefined();
    });

    it('should set API key info correctly', () => {
      const keyInfo = client.getAPIKeyInfo();
      expect(keyInfo).toBe('test-api-key...');
    });

    it('should handle missing API key', () => {
      const clientWithoutKey = new CodeAtlasAPIClient();
      expect(clientWithoutKey.getAPIKeyInfo()).toBeNull();
    });
  });

  describe('API requests', () => {
    it('should make discover sessions API call', async () => {
      const mockResponse = {
        sessions: [
          {
            path: '/test/session.jsonl',
            filename: 'session.jsonl',
            size_bytes: 1024,
            modified_at: '2025-01-01T00:00:00Z',
            project_name: 'test-project'
          }
        ],
        total_found: 1,
        search_path: '/test',
        message: 'Found 1 sessions'
      };

      (fetch as any).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse)
      });

      const result = await client.discoverSessions({ limit: 10 });

      expect(fetch).toHaveBeenCalledWith(
        'http://test-api/api/v1/sessions/discover',
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-API-Key': 'test-api-key'
          },
          body: JSON.stringify({ limit: 10 })
        }
      );

      expect(result).toEqual(mockResponse);
    });

    it('should submit sessions for processing', async () => {
      const mockResponse = {
        job: {
          job_id: 'test-job-id',
          status: 'pending',
          total_sessions: 1,
          processed_sessions: 0,
          failed_sessions: 0
        },
        message: 'Processing job created'
      };

      (fetch as any).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse)
      });

      const result = await client.processSessions({
        session_paths: ['/test/session.jsonl'],
        use_llm: true,
        dry_run: false,
        max_cost_per_session: 0.02
      });

      expect(fetch).toHaveBeenCalledWith(
        'http://test-api/api/v1/sessions/process',
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-API-Key': 'test-api-key'
          },
          body: JSON.stringify({
            session_paths: ['/test/session.jsonl'],
            use_llm: true,
            dry_run: false,
            max_cost_per_session: 0.02
          })
        }
      );

      expect(result).toEqual(mockResponse);
    });

    it('should get job status', async () => {
      const mockResponse = {
        job: {
          job_id: 'test-job-id',
          status: 'completed',
          total_sessions: 1,
          processed_sessions: 1,
          failed_sessions: 0
        },
        message: 'Job completed'
      };

      (fetch as any).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse)
      });

      const result = await client.getJobStatus('test-job-id');

      expect(fetch).toHaveBeenCalledWith(
        'http://test-api/api/v1/sessions/test-job-id/status',
        {
          headers: {
            'Content-Type': 'application/json',
            'X-API-Key': 'test-api-key'
          }
        }
      );

      expect(result).toEqual(mockResponse);
    });
  });

  describe('error handling', () => {
    it('should handle API errors gracefully', async () => {
      (fetch as any).mockResolvedValueOnce({
        ok: false,
        status: 400,
        json: () => Promise.resolve({ detail: 'Bad request' })
      });

      await expect(client.discoverSessions({ limit: 10 })).rejects.toThrow('Bad request');
    });

    it('should handle missing error detail', async () => {
      (fetch as any).mockResolvedValueOnce({
        ok: false,
        status: 500,
        statusText: 'Internal Server Error',
        json: () => Promise.reject(new Error('JSON parse error'))
      });

      await expect(client.discoverSessions({ limit: 10 })).rejects.toThrow('HTTP 500: Internal Server Error');
    });
  });

  describe('connection testing', () => {
    it('should return true for successful connection', async () => {
      (fetch as any).mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ service: 'Code Atlas API' })
      });

      const result = await client.testConnection();
      expect(result).toBe(true);
    });

    it('should return false for failed connection', async () => {
      (fetch as any).mockRejectedValueOnce(new Error('Network error'));

      const result = await client.testConnection();
      expect(result).toBe(false);
    });
  });
});