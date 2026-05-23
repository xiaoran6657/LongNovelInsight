// Health
export interface HealthResponse {
  status: string;
  version: string;
  topic_count: number;
  total_disk_usage_bytes: number;
}

// Providers
export interface ModelProvider {
  id: string;
  name: string;
  provider_type: string;
  base_url: string;
  model_name: string;
  context_window: number;
  max_output_tokens: number;
  temperature: number;
  is_default: boolean;
  masked_api_key: string;
  created_at: string;
  updated_at: string;
}

export interface ModelProviderCreate {
  name: string;
  provider_type: string;
  base_url: string;
  api_key: string;
  model_name?: string;
  context_window?: number;
  max_output_tokens?: number;
  temperature?: number;
  is_default?: boolean;
}

export interface ModelProviderUpdate {
  name?: string;
  provider_type?: string;
  base_url?: string;
  api_key?: string;
  model_name?: string;
  context_window?: number;
  max_output_tokens?: number;
  temperature?: number;
  is_default?: boolean;
}

// Provider Presets
export interface ProviderModelPreset {
  model_name: string;
  display_name: string;
  context_window?: number | null;
  max_output_tokens?: number | null;
  recommended_max_output_tokens?: number | null;
  default_temperature?: number | null;
  supports_json_output: boolean;
  supports_thinking: boolean;
  default_thinking_mode: string;
  notes?: string | null;
  tags: string[];
}

export interface ProviderBaseUrlPreset {
  label: string;
  base_url: string;
  region?: string | null;
  provider_key: string;
}

export interface ProviderPreset {
  provider_key: string;
  display_name: string;
  api_format: string;
  base_urls: ProviderBaseUrlPreset[];
  models: ProviderModelPreset[];
  default_model_name?: string | null;
}

export interface ProviderTestResult {
  success: boolean;
  provider_id: string;
  model_name: string;
  latency_ms: number;
  message: string;
}

// Topics
export interface Topic {
  id: string;
  name: string;
  description: string | null;
  provider_id: string | null;
  storage_bytes: number;
  status: string;
  document: DocumentSummary | null;
  analysis_summary: Record<string, string>;
  disk_usage_bytes: number;
  created_at: string;
  updated_at: string;
}

export interface TopicCreate {
  name: string;
  description?: string;
  provider_id?: string;
}

export interface DocumentSummary {
  id: string;
  original_filename: string;
  status: string;
  file_size_bytes: number;
  char_count: number;
}

// Documents
export interface Document {
  id: string;
  topic_id: string;
  original_filename: string;
  stored_filename: string;
  file_type: string;
  content_type: string | null;
  encoding: string;
  file_size_bytes: number;
  char_count: number;
  storage_path: string;
  status: string;
  created_at: string;
  updated_at: string;
}

// Parse
export interface ParseResult {
  already_parsed?: boolean;
  chapter_count: number;
  chunk_count: number;
  char_count: number;
  estimated_tokens: number;
  has_outputs?: boolean;
  warning?: string;
}

export interface Chapter {
  id: string;
  topic_id: string;
  document_id: string;
  chapter_index: number;
  title: string;
  start_char: number;
  end_char: number;
  char_count: number;
  created_at: string;
}

export interface Chunk {
  id: string;
  chapter_index: number;
  chunk_index: number;
  text: string;
  start_char: number;
  end_char: number;
  char_count: number;
  estimated_tokens: number;
}

export interface StorageInfo {
  total_disk_usage_bytes: number;
  database_size_bytes: number;
  data_dir_size_bytes: number;
  topics: {
    topic_id: string;
    topic_name: string;
    novel_size_bytes: number;
    chunks_size_bytes: number;
    analyses_size_bytes: number;
    total_bytes: number;
  }[];
}

// Analysis
export interface AnalysisOutput {
  id: string;
  topic_id: string;
  job_id: string | null;
  run_id?: string | null;
  output_type: string;
  title: string;
  content_json: Record<string, unknown> | null;
  source_chunk_ids: string[];
  evidence_quotes: string[];
  confidence: number;
  prompt_tokens: number;
  completion_tokens: number;
  created_at: string;
  updated_at: string;
}

export interface Job {
  id: string;
  topic_id: string;
  job_type: string;
  status: string;
  progress_current: number;
  progress_total: number;
  message: string | null;
  error_message: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface JobItem {
  id: string;
  job_id: string;
  item_type: string;
  status: string;
  progress_current: number;
  progress_total: number;
  message: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

// Topic Provider Config
export interface TopicProviderConfigData {
  id?: string;
  topic_id: string;
  provider_id?: string | null;
  base_url_override?: string | null;
  model_name_override?: string | null;
  context_window_override?: number | null;
  max_output_tokens_override?: number | null;
  temperature_override?: number | null;
  thinking_mode_override?: string | null;
  reasoning_effort_override?: string | null;
  analysis_parallelism_override?: number | null;
  recommended_profile?: string | null;
}

export interface EffectiveProviderConfig {
  provider_id?: string | null;
  provider_name?: string | null;
  provider_key?: string | null;
  base_url?: string | null;
  model_name?: string | null;
  context_window?: number | null;
  max_output_tokens?: number | null;
  temperature?: number | null;
  thinking_mode: string;
  reasoning_effort?: string | null;
  analysis_parallelism: number;
  supports_json_output: boolean;
  supports_thinking: boolean;
  is_ready: boolean;
  missing_fields: string[];
  warnings: string[];
}

export interface AnalysisRecommendation {
  size_category: string;
  total_chars?: number | null;
  estimated_input_tokens?: number | null;
  chunk_count?: number | null;
  recommended_model_name?: string | null;
  recommended_context_window?: number | null;
  recommended_max_output_tokens: number;
  recommended_temperature: number;
  recommended_thinking_mode: string;
  recommended_parallelism: number;
  recommended_limit_chunks?: number | null;
  recommended_analysis_mode: string;
  warnings: string[];
  rationale: string[];
}

// Chat
export interface ChatSessionRead {
  id: string;
  topic_id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface ChatMessageRead {
  id: string;
  session_id: string;
  role: string;
  content: string;
  evidence_json: string | null;
  uncertainty: string | null;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  model_used: string | null;
  created_at: string;
}

export interface ChatAnswerRead {
  id: string;
  session_id: string;
  role: string;
  content: string;
  evidence_json: unknown;
  uncertainty: string | null;
  created_at: string;
}

// ── v0.2 Analysis Run types ──

export type AnalysisMode = "preview" | "range" | "full" | "incremental";

export type AnalysisRunStatus =
  | "pending"
  | "running"
  | "succeeded"
  | "partial_success"
  | "failed"
  | "cancelled";

export type AnalysisStage = "extraction" | "merge" | "final";

export interface ChunkSelectionParams {
  mode: AnalysisMode;
  selected: number;
  total: number;
  limit_chunks?: number;
  range_start?: number;
  range_end?: number;
  chapter_start?: number;
  chapter_end?: number;
}

export interface ChunksByChapter {
  chapter_index: number;
  title: string;
  chunk_count: number;
  char_count: number;
  estimated_tokens: number;
}

export interface ChunksMetaResponse {
  topic_id: string;
  document_id: string | null;
  chunk_count: number;
  chapter_count: number;
  total_chars: number;
  estimated_tokens: number;
  first_chunk_index: number | null;
  last_chunk_index: number | null;
  first_global_chunk_index: number | null;
  last_global_chunk_index: number | null;
  chunks_by_chapter: ChunksByChapter[];
}

export interface AnalysisRunCreateRequest {
  mode: AnalysisMode;
  requested_types?: string[];
  limit_chunks?: number;
  chunk_index_start?: number;
  chunk_index_end?: number;
  chapter_index_start?: number;
  chapter_index_end?: number;
  force?: boolean;
  start_immediately?: boolean;
}

export interface ExtractionSummary {
  id: string;
  chunk_id: string;
  status: string;
  attempt_count: number;
  error_message: string | null;
}

export interface MergeOutputSummary {
  id: string;
  output_type: string;
  title: string;
}

export interface MergeStageSummary {
  total: number;
  succeeded: number;
  failed: number;
  outputs: MergeOutputSummary[];
  warnings: string[];
}

export interface FinalStageSummary {
  total: number;
  succeeded: number;
  failed: number;
  outputs: MergeOutputSummary[];
}

// POST /api/topics/{id}/analysis/runs response
export interface AnalysisRunCreateSummary {
  id: string;
  topic_id: string;
  mode: AnalysisMode;
  status: AnalysisRunStatus;
  progress_total: number;
}

// GET /api/topics/{id}/analysis/runs list item
export interface AnalysisRunListItem {
  id: string;
  mode: AnalysisMode;
  status: AnalysisRunStatus;
  extraction_succeeded: number;
  extraction_failed: number;
  merge_succeeded: number;
  merge_failed: number;
  total_tokens: number;
  model_used: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string | null;
}

// GET /api/analysis/runs/{id} full detail
export interface AnalysisRun {
  id: string;
  topic_id: string;
  mode: AnalysisMode;
  status: AnalysisRunStatus;
  progress_current: number;
  progress_total: number;
  extraction_total: number;
  extraction_succeeded: number;
  extraction_failed: number;
  merge_total: number;
  merge_succeeded: number;
  merge_failed: number;
  final_total?: number;
  final_succeeded?: number;
  final_failed?: number;
  total_tokens: number;
  model_used: string | null;
  error_message: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at?: string | null;
}

export interface AnalysisRunDetail {
  run: AnalysisRun;
  extractions: ExtractionSummary[];
  merge: MergeStageSummary;
  final: FinalStageSummary;
}

export interface AnalysisRunListResponse {
  runs: AnalysisRunListItem[];
}

export interface CreateAnalysisRunResponse {
  run: AnalysisRunCreateSummary;
  status_url: string;
}

export interface RunRetryResponse {
  run: { id: string; status: string };
  message: string;
}

export interface RunResumeResponse {
  run: { id: string; status: string };
  message: string;
}

export interface RunCancelResponse {
  run: { id: string; status: string };
}

export interface LatestV2RunSummary {
  id: string;
  mode: AnalysisMode;
  status: AnalysisRunStatus;
  progress_current: number;
  progress_total: number;
  extraction_succeeded: number;
  extraction_failed: number;
  merge_succeeded: number;
  merge_failed: number;
  final_succeeded?: number;
  final_failed?: number;
  total_tokens: number;
  model_used: string | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string | null;
}

// Updated v0.2 AnalysisStatusResponse
export interface AnalysisStatusV2Response {
  topic_id: string;
  has_jobs: boolean;
  has_outputs: boolean;
  latest_job: Job | null;
  analysis_types_completed: string[];
  output_counts_by_type: Record<string, number>;
  latest_v2_run: LatestV2RunSummary | null;
  v2_available: boolean;
}
