/* API types matching backend schemas */

export enum EntityType {
  SESSION = 'Session',
  CONCEPT = 'Concept',
  FILE = 'File',
  TOOL = 'Tool',
  PROBLEM = 'Problem',
  SOLUTION = 'Solution',
}

export enum RelationshipType {
  MENTIONS = 'MENTIONS',
  REFERENCES = 'REFERENCES',
  SOLVES = 'SOLVES',
  USES = 'USES',
  RELATED_TO = 'RELATED_TO',
}

export enum JobStatus {
  PENDING = 'pending',
  RUNNING = 'running',
  COMPLETED = 'completed',
  FAILED = 'failed',
  CANCELLED = 'cancelled',
}

export enum APIKeyScope {
  READ = 'read',
  WRITE = 'write',
  PROCESS = 'process',
  ADMIN = 'admin',
}

// Base interfaces
export interface BaseEntity {
  id: string;
  type: EntityType;
  name: string;
  properties?: Record<string, any>;
  confidence?: number;
  source_session?: string;
  created_at?: string;
  mention_count?: number;
}

export interface BaseRelationship {
  id: string;
  type: RelationshipType;
  source_id: string;
  source_name: string;
  source_type: EntityType;
  target_id: string;
  target_name: string;
  target_type: EntityType;
  properties?: Record<string, any>;
  confidence?: number;
  created_at?: string;
}

// Session types
export interface SessionInfo {
  path: string;
  filename: string;
  size_bytes: number;
  modified_at: string;
  project_name: string;
}

export interface SessionDiscoveryRequest {
  root_path?: string;
  project_filter?: string;
  limit: number;
  min_size_bytes?: number;
  max_size_bytes?: number;
  modified_after?: string;
  modified_before?: string;
}

export interface SessionDiscoveryResponse {
  sessions: SessionInfo[];
  total_found: number;
  search_path: string;
  message: string;
}

export interface ProcessingJob {
  job_id: string;
  status: JobStatus;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  total_sessions: number;
  processed_sessions: number;
  failed_sessions: number;
  current_session?: string;
  error_message?: string;
  stats?: ProcessingStats;
}

export interface ProcessingStats {
  entities_created: number;
  relationships_created: number;
  total_cost_usd: number;
}

export interface SessionProcessRequest {
  session_paths: string[];
  use_llm: boolean;
  dry_run: boolean;
  max_cost_per_session: number;
}

export interface SessionProcessResponse {
  job: ProcessingJob;
  message: string;
}

export interface ProcessingStatsResponse {
  total_jobs: number;
  total_sessions_processed: number;
  total_entities_created: number;
  total_relationships_created: number;
  total_cost_usd: number;
  avg_processing_time_seconds: number;
  success_rate: number;
}

// Graph types
export type EntityResponse = BaseEntity

export interface EntityListResponse {
  entities: EntityResponse[];
  total: number;
  page: number;
  page_size: number;
  message: string;
}

export interface EntitySearchResult {
  entity: EntityResponse;
  score: number;
  highlights: string[];
}

export interface EntitySearchResponse {
  results: EntitySearchResult[];
  total: number;
  query: string;
  took_ms: number;
  message: string;
}

export type RelationshipResponse = BaseRelationship

export interface RelationshipListResponse {
  relationships: RelationshipResponse[];
  total: number;
  page: number;
  page_size: number;
  message: string;
}

export interface GraphQueryRequest {
  query: string;
  parameters?: Record<string, any>;
  limit: number;
}

export interface GraphQueryResponse {
  results: Record<string, any>[];
  columns: string[];
  row_count: number;
  execution_time_ms: number;
  message: string;
}

export interface NodeData {
  id: string;
  label: string;
  type: EntityType;
  size: number;
  color: string;
  properties: Record<string, any>;
}

export interface EdgeData {
  id: string;
  source: string;
  target: string;
  type: RelationshipType;
  weight: number;
  color: string;
  properties: Record<string, any>;
}

export interface GraphVisualizationResponse {
  nodes: NodeData[];
  edges: EdgeData[];
  node_count: number;
  edge_count: number;
  layout_hint: string;
  message: string;
}

export interface GraphStatsResponse {
  total_nodes: number;
  total_edges: number;
  nodes_by_type: Record<string, number>;
  edges_by_type: Record<string, number>;
  avg_connections_per_node: number;
  most_connected_entities: EntityResponse[];
  message: string;
}

// API Key types
export interface APIKeyRecord {
  key_id: string;
  name: string;
  key_hash: string;
  key_prefix: string;
  scopes: APIKeyScope[];
  is_active: boolean;
  created_at: string;
  expires_at?: string;
  last_used_at?: string;
  request_count: number;
}

export interface APIKeyCreateRequest {
  name: string;
  scopes: APIKeyScope[];
  expires_in_days?: number;
}

export interface APIKeyCreateResponse {
  key_id: string;
  raw_key: string;
  name: string;
  scopes: APIKeyScope[];
  expires_at?: string;
}

export interface APIKeyInfo {
  key_id: string;
  name: string;
  key_prefix: string;
  scopes: APIKeyScope[];
  is_active: boolean;
  created_at: string;
  expires_at?: string;
  last_used_at?: string;
  request_count: number;
}

export interface APIKeyUsageStats {
  key_id: string;
  name: string;
  request_count: number;
  last_used_at?: string;
  requests_today: number;
  rate_limit_remaining: number;
}

// Common request parameters
export interface EntityListParams {
  entity_type?: EntityType;
  search?: string;
  min_confidence?: number;
  page?: number;
  page_size?: number;
}

export interface SearchParams {
  entity_type?: EntityType;
  fuzzy?: boolean;
  min_score?: number;
  limit?: number;
}

export interface VisualizationParams {
  entity_type?: EntityType;
  center_entity_id?: string;
  depth?: number;
  max_nodes?: number;
}

export interface QueryParams {
  limit?: number;
}

// RAG types
export interface RAGQueryRequest {
  question: string;
  entity_type?: EntityType;
  context_limit?: number;
  include_sources?: boolean;
}

export interface RAGQueryResponse {
  success: boolean;
  answer: string;
  sources: string[];
  confidence: number;
  context_entities: Array<{
    entity_id: string;
    entity_name: string;
    entity_type: string;
  }>;
  search_results_count: number;
  execution_time_ms: number;
  message: string;
}

// Hybrid search types
export interface HybridSearchRequest {
  query: string;
  entity_type?: EntityType;
  limit?: number;
  min_score?: number;
  graph_weight?: number;
  vector_weight?: number;
  use_graph_structure?: boolean;
  use_vector_search?: boolean;
}

export interface HybridSearchResultItem {
  entity_id: string;
  entity_name: string;
  entity_type: string;
  graph_score: number;
  vector_score: number;
  combined_score: number;
  metadata: Record<string, any>;
}

export interface HybridSearchResponse {
  success: boolean;
  results: HybridSearchResultItem[];
  total: number;
  query: string;
  execution_time_ms: number;
  message: string;
}