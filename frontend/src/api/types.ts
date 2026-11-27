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

// E1 US2 – chi tiết ngách (openapi NicheDetail)
export type VerificationStatus = 'VERIFIED' | 'INFERRED' | 'UNKNOWN' | 'CONFLICTING'
export interface ConflictValue {
  value: unknown
  evidence_ids: string[]
}
export interface Finding {
  value: unknown
  status: VerificationStatus
  evidence_ids: string[]
}
export interface PainPoint {
  id: string
  title: string
  description: string
  severity: number | null
  severity_reason?: string | null
  evidence_count: number
  status: VerificationStatus
}
export interface Competitor {
  name: string
  kind: 'PRODUCT' | 'SERVICE' | 'MANUAL_WORKAROUND'
  url: string | null
  strengths: string[]
  weaknesses: string[]
}
export interface NicheEvidence {
  id: string
  source_url: string
  source_domain: string | null
  excerpt: string
  collected_at: string
  published_at?: string | null
  verification_status: VerificationStatus
  redaction_status: 'REDACTED' | 'NEEDS_REVIEW'
  purpose: string | null
  relevance: number | null
  quality: number | null
  independence_group: string
  counted_for_threshold: boolean
  policy_verified_at: string | null
  data_origin: 'REAL' | 'MOCK'
}
export interface NicheDetail {
  id: string
  name: string
  micro_niche: string
  country: string
  customer_group: string
  core_problem: string
  opportunity_score: number | null
  confidence_score: number | null
  evidence_status: 'EVIDENCE_SUFFICIENT' | 'INSUFFICIENT_EVIDENCE'
  monetization_status: 'SIGNALS_FOUND' | 'MONETIZATION_UNVERIFIED' | 'NO_AFFILIATE_FOUND'
  risk_flags: string[]
  ai_recommendation: 'PURSUE' | 'REJECT' | 'UNKNOWN'
  decision_status: string
  data_origin: 'REAL' | 'MOCK'
  disclaimer_key: string
  pain_points: PainPoint[]
  persona: Record<string, Finding>
  findings: Record<string, Finding>
  competitors: Competitor[]
  evidence: NicheEvidence[]
  latest_evaluation: Evaluation | null
  ai_recommendation_reason?: string
  possible_duplicates?: SimilarityPair[]
  has_possible_duplicate?: boolean
  opportunity_disclaimer_key?: string
  run_ids: string[]
}
export interface EraseResponse {
  erasure_id: string
  affected_niche_ids: string[]
  recompute_job: { job_id: string; job_type: string; status: string } | null
}

// E1 US3 – xếp hạng (openapi NicheSummary)
export type RankingList = 'research' | 'affiliate' | 'needs_research'
export interface NicheSummary {
  id: string
  name: string
  micro_niche: string
  country: string
  opportunity_score: number | null
  confidence_score: number | null
  coverage: number | null
  scoring_status: 'SCORED' | 'INSUFFICIENT_SCORING_DATA' | null
  evidence_status: 'EVIDENCE_SUFFICIENT' | 'INSUFFICIENT_EVIDENCE'
  verification_summary: Record<string, number>
  monetization_status: 'SIGNALS_FOUND' | 'MONETIZATION_UNVERIFIED' | 'NO_AFFILIATE_FOUND'
  risk_flags: string[]
  ai_recommendation: 'PURSUE' | 'REJECT' | 'UNKNOWN'
  decision_status: string
  has_possible_duplicate: boolean
  data_origin: 'REAL' | 'MOCK'
}
export interface CriterionResult {
  score: number | null
  status: VerificationStatus
  weight: number
  normalized_weight: number | null
  reason: string
  evidence_ids: string[]
}
export interface Evaluation {
  id: string
  run_id: string | null
  weights_version: number
  criteria: Record<string, CriterionResult>
  coverage: number
  scoring_status: 'SCORED' | 'INSUFFICIENT_SCORING_DATA'
  opportunity_score: number | null
  confidence_score: number
  confidence_components: Record<string, number>
  missing_data: string[]
  computed_without_ai: boolean
  data_origin: 'REAL' | 'MOCK'
  created_at: string
}

// E1 US4 – hồ sơ tuân thủ nguồn (openapi SourcePolicy)
export interface SourcePolicy {
  id: string
  source_key: string
  display_name: string
  adapter_type: string
  config: Record<string, unknown>
  tos_url: string
  verified_at: string | null
  verification_note: string | null
  allowed_access_methods: string[]
  permitted_use_scope: string | null
  compliance_status: 'ALLOWED' | 'UNVERIFIED' | 'PROHIBITED'
  known_limits: string | null
  enabled: boolean
  usable: boolean
  verified_by: string | null
  requires_service_restart: boolean
}
export interface SourceUpdate {
  compliance_status?: 'ALLOWED' | 'UNVERIFIED' | 'PROHIBITED'
  verified_at?: string
  verification_note?: string
  allowed_access_methods?: string[]
  permitted_use_scope?: string
  enabled?: boolean
}

// E1 US5 – cặp ngách có thể tương đồng
export interface SimilarityPair {
  id: string
  niche_a_id: string
  niche_b_id: string
  niche_a_name?: string | null
  niche_b_name?: string | null
  score: number
  status: 'POSSIBLE' | 'CONFIRMED_DUPLICATE' | 'NOT_DUPLICATE'
}

// ---------------------------------------------------------------------------------------------------------------------
// E2 – Product & Affiliate Discovery (specs/003-product-affiliate-discovery/contracts/openapi.yaml)
// ---------------------------------------------------------------------------------------------------------------------
export type AttrStatus = 'VERIFIED' | 'INFERRED' | 'CONFLICTING' | 'UNKNOWN'
export type Readiness =
  | 'READY_TO_PROMOTE'
  | 'ELIGIBILITY_UNVERIFIED'
  | 'NOT_ELIGIBLE'
  | 'AFFILIATE_UNVERIFIED'
  | 'NO_PROGRAM'
  | 'PROGRAM_CLOSED'
export type ProductList = 'ranked' | 'needs_research'
export type ProductDecision = 'CANDIDATE' | 'SELECTED' | 'WATCH' | 'REJECTED'

export interface ProductCriterion {
  level: number | null
  status: string
  reason: string
  evidence_ids: string[]
}

export interface ProductEvaluation {
  opportunity_score: number | null
  confidence_score: number | null
  coverage: number | null
  scoring_status: 'SCORED' | 'INSUFFICIENT_SCORING_DATA'
  criteria: Record<string, ProductCriterion>
  missing: string[]
  weights_version: number | null
  computed_at: string | null
}

export interface ProductItem {
  product_id: string
  name: string
  vendor: string | null
  official_domain: string | null
  category: string
  readiness_status: Readiness
  risk_flags: string[]
  evaluation: ProductEvaluation | null
  ai_recommendation: 'SELECT' | 'REJECT' | 'UNKNOWN'
  ai_recommendation_reason: string | null
  decision_status: ProductDecision
  decision_reason: string | null
  persona_match: string
  data_origin: 'REAL' | 'MOCK'
}

export interface AttributeValue {
  value: unknown
  status: string
  evidence_id: string
  source_url: string | null
  excerpt: string | null
  collected_at: string | null
  verified_at: string | null
}

export interface ProductAttribute {
  key: string
  status: AttrStatus
  value: unknown
  flags: string[]
  values: AttributeValue[]
}

export interface TermsVersion {
  version: number
  checked_at: string
  changes: { claim_key: string; old: unknown; new: unknown }[]
  acknowledged_at: string | null
}

export interface AffiliateProgram {
  program_id: string
  name: string
  operator_type: string
  operator_name: string | null
  operator_domain: string | null
  terms_url: string | null
  verification_status: 'VERIFIED' | 'PARTIAL' | 'UNVERIFIED' | 'CLOSED'
  attributes: ProductAttribute[]
  watch_enabled: boolean
  last_checked_at: string | null
  last_check_error: string | null
  terms_versions: TermsVersion[]
  data_origin: 'REAL' | 'MOCK'
}

export interface ProductDetail extends ProductItem {
  attributes: ProductAttribute[]
  pain_points: { pain_point_id: string; title: string; evidence: { evidence_id: string; excerpt: string; source_url: string | null }[] }[]
  programs: AffiliateProgram[]
  disclaimer_key: string
}

export interface ProductSummary {
  products: number
  programs_verified: number
  ready_to_promote: number
  monetization_risk: boolean
  last_run_id: string | null
}
