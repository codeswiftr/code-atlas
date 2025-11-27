import {
  SessionDiscoveryRequest,
  SessionDiscoveryResponse,
  SessionProcessRequest,
  SessionProcessResponse,
  ProcessingJob,
  EntityListParams,
  EntityListResponse,
  SearchParams,
  EntitySearchResponse,
  VisualizationParams,
  GraphVisualizationResponse,
  GraphQueryRequest,
  GraphQueryResponse,
  QueryParams,
} from '@/types/api';

/**
 * Code Atlas API client
 * Provides methods to interact with the Code Atlas backend API
 */
export class CodeAtlasAPIClient {
  private baseURL: string;
  private apiKey?: string;
  private wsBaseURL: string;

  constructor(baseURL: string = 'http://localhost:8000', apiKey?: string) {
    this.baseURL = baseURL;
    this.apiKey = apiKey;
    this.wsBaseURL = baseURL.replace('http', 'ws');
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseURL}${endpoint}`;
    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      ...options.headers,
    };

    if (this.apiKey) {
      headers['X-API-Key'] = this.apiKey;
    }

    const response = await fetch(url, {
      ...options,
      headers,
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.detail || `HTTP ${response.status}: ${response.statusText}`);
    }

    return response.json();
  }

  /**
   * Discover available sessions with filters
   */
  async discoverSessions(request: SessionDiscoveryRequest): Promise<SessionDiscoveryResponse> {
    return this.request<SessionDiscoveryResponse>('/api/v1/sessions/discover', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  /**
   * Submit sessions for processing
   */
  async processSessions(request: SessionProcessRequest): Promise<SessionProcessResponse> {
    return this.request<SessionProcessResponse>('/api/v1/sessions/process', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  /**
   * Get processing job status
   */
  async getJobStatus(jobId: string): Promise<SessionProcessResponse> {
    return this.request<SessionProcessResponse>(`/api/v1/sessions/${jobId}/status`);
  }

  /**
   * List processing jobs
   */
  async listJobs(statusFilter?: string, limit: number = 20): Promise<ProcessingJob[]> {
    const params = new URLSearchParams();
    if (statusFilter) params.append('status', statusFilter);
    params.append('limit', limit.toString());

    return this.request<ProcessingJob[]>(`/api/v1/sessions?${params}`);
  }

  /**
   * Cancel a processing job
   */
  async cancelJob(jobId: string): Promise<void> {
    await this.request<void>(`/api/v1/sessions/${jobId}`, {
      method: 'DELETE',
    });
  }

  /**
   * Get processing statistics
   */
  async getProcessingStats(): Promise<any> {
    return this.request<any>('/api/v1/sessions/stats');
  }

  /**
   * List entities with pagination and filters
   */
  async listEntities(params: EntityListParams = {}): Promise<EntityListResponse> {
    const searchParams = new URLSearchParams();
    
    if (params.entity_type) searchParams.append('type', params.entity_type);
    if (params.search) searchParams.append('search', params.search);
    if (params.min_confidence) searchParams.append('min_confidence', params.min_confidence.toString());
    if (params.page) searchParams.append('page', params.page.toString());
    if (params.page_size) searchParams.append('page_size', params.page_size.toString());

    return this.request<EntityListResponse>(`/api/v1/graph/entities?${searchParams}`);
  }

  /**
   * Search entities with fuzzy matching
   */
  async searchEntities(
    query: string,
    params: SearchParams = {}
  ): Promise<EntitySearchResponse> {
    const searchParams = new URLSearchParams();
    searchParams.append('q', query);
    
    if (params.entity_type) searchParams.append('type', params.entity_type);
    if (params.fuzzy !== undefined) searchParams.append('fuzzy', params.fuzzy.toString());
    if (params.min_score) searchParams.append('min_score', params.min_score.toString());
    if (params.limit) searchParams.append('limit', params.limit.toString());

    return this.request<EntitySearchResponse>(`/api/v1/graph/entities/search?${searchParams}`);
  }

  /**
   * Get single entity by ID
   */
  async getEntity(entityId: string): Promise<any> {
    return this.request<any>(`/api/v1/graph/entities/${entityId}`);
  }

  /**
   * List relationships
   */
  async listRelationships(params: {
    rel_type?: string;
    source_id?: string;
    target_id?: string;
    page?: number;
    page_size?: number;
  } = {}): Promise<any> {
    const searchParams = new URLSearchParams();
    
    if (params.rel_type) searchParams.append('type', params.rel_type);
    if (params.source_id) searchParams.append('source_id', params.source_id);
    if (params.target_id) searchParams.append('target_id', params.target_id);
    if (params.page) searchParams.append('page', params.page.toString());
    if (params.page_size) searchParams.append('page_size', params.page_size.toString());

    return this.request<any>(`/api/v1/graph/relationships?${searchParams}`);
  }

  /**
   * Execute Cypher query (read-only)
   */
  async executeQuery(request: GraphQueryRequest): Promise<GraphQueryResponse> {
    return this.request<GraphQueryResponse>('/api/v1/graph/query', {
      method: 'POST',
      body: JSON.stringify(request),
    });
  }

  /**
   * Get graph visualization data
   */
  async getVisualization(params: VisualizationParams = {}): Promise<GraphVisualizationResponse> {
    const searchParams = new URLSearchParams();
    
    if (params.entity_type) searchParams.append('type', params.entity_type);
    if (params.center_entity_id) searchParams.append('center_entity_id', params.center_entity_id);
    if (params.depth) searchParams.append('depth', params.depth.toString());
    if (params.max_nodes) searchParams.append('max_nodes', params.max_nodes.toString());

    return this.request<GraphVisualizationResponse>(`/api/v1/graph/visualization?${searchParams}`);
  }

  /**
   * Get graph statistics
   */
  async getGraphStats(): Promise<any> {
    return this.request<any>('/api/v1/graph/stats');
  }

  /**
   * Create WebSocket connection for real-time updates
   */
  createJobStatusWebSocket(jobId: string): WebSocket {
    const wsURL = `${this.wsBaseURL}/ws/jobs/${jobId}`;
    return new WebSocket(wsURL);
  }

  /**
   * Set API key for authentication
   */
  setAPIKey(apiKey: string): void {
    this.apiKey = apiKey;
  }

  /**
   * Get current API key (masked)
   */
  getAPIKeyInfo(): string | null {
    if (!this.apiKey) return null;
    return `${this.apiKey.substring(0, 12)}...`;
  }

  /**
   * Test API connection
   */
  async testConnection(): Promise<boolean> {
    try {
      await this.request<any>('/');
      return true;
    } catch {
      return false;
    }
  }
}

// Create default client instance
export const apiClient = new CodeAtlasAPIClient();