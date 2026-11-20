// Kiểu dữ liệu theo contracts/openapi.yaml (phần dùng trong E0).
import type { Locale } from '../i18n'

export interface Me {
  id: string
  username: string
  ui_locale: Locale
  last_login_at: string | null
}

export interface ProviderStatus {
  provider: 'anthropic' | 'openai' | 'mock'
  configured: boolean
  key_hint: string | null
  last_check: string | null
}

export type ComponentState = 'OK' | 'UNAVAILABLE' | 'STALE' | 'NOT_RUNNING'

export interface SystemStatus {
  version: string
  app_env: 'development' | 'test' | 'production'
  database: ComponentState
  worker: ComponentState
  schema_revision: string | null
  paid_calls_enabled: boolean
  provider_override: string | null
  providers: ProviderStatus[]
  log_storage?: { retention_days: number; warning: boolean } | null
}

// E1 – Autonomous Niche Discovery (specs/002-niche-discovery/contracts/openapi.yaml)
export type RunOutcome = 'COMPLETED' | 'PARTIAL_COMPLETED'
export type StopReason =
  | 'ALL_CANDIDATES_SUFFICIENT'
  | 'CANDIDATES_EXHAUSTED'
  | 'TIME_LIMIT_REACHED'
  | 'PAGE_LIMIT_REACHED'
  | 'NO_COMPLIANT_SEARCH_SOURCE'
  | 'SOURCES_UNAVAILABLE'
  | 'CANCELLED'

export interface DiscoveryRun {
  id: string
  job: { job_id: string; job_type: string; status: string }
  market: string
  research_language: string
  seed_topic: string | null
  max_candidates: number
  budget_usd: string
  time_limit_minutes: number
  page_limit: number
  per_domain_interval_s: number
  weights_version: number
  source_mode: 'REAL' | 'MOCK'
  trigger: 'MANUAL' | 'SCHEDULE' | 'RETRY'
  sources: { source_key: string; verified_at: string | null }[]
  outcome: RunOutcome | null
  stop_reason: StopReason | null
  metrics: Record<string, unknown>
  data_origin: 'REAL' | 'MOCK'
  created_at: string
}

export interface DiscoveryRunCreate {
  market: string
  research_language?: string
  seed_topic?: string | null
  max_candidates?: number
  budget_usd?: string
}
