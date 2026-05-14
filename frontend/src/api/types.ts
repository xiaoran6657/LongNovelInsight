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
  model_name: string;
  context_window?: number;
  max_output_tokens?: number;
  temperature?: number;
  is_default?: boolean;
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
  chapter_count: number;
  chunk_count: number;
  char_count: number;
  estimated_tokens: number;
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
  output_type: string;
  title: string;
  content_json: Record<string, unknown> | null;
  source_chunk_ids: string[];
  evidence_quotes: string[];
  confidence: number;
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
