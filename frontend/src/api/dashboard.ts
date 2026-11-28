// E4 – hook API dashboard: Tổng quan, ngách kèm tóm tắt E2/E3, Agent Jobs, lịch chạy, chi phí, cấu hình (API E0–E4 sẵn có).
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/api/client'

const flag = (v: boolean) => (v ? 'true' : 'false')

export interface Overview {
  niches: { total: number; by_evidence_status: Record<string, number>; by_decision: Record<string, number> }
  products: { total: number; ready_to_promote: number }
  keywords: { total: number; clusters: number; long_tail: number }
  jobs: { by_status: Record<string, number>; failed_7d: number }
  top_niches: { niche_id: string; name: string; opportunity_score: number | null; confidence_score: number | null; data_origin: 'REAL' | 'MOCK' }[]
  include_mock: boolean
  generated_at: string
}

export interface ResearchNiche {
  niche_id: string
  name: string
  country: string
  evidence_status: string
  decision_status: string
  eligible: boolean
  opportunity_score: number | null
  confidence_score: number | null
  products: { has_run: boolean; total: number; ready_to_promote: number }
  keywords: {
    has_run: boolean
    total: number
    clusters: number
    long_tail: number
    best_cluster: { cluster_id: string; name: string; opportunity_score: number | null; confidence_score: number | null } | null
  }
  data_origin: 'REAL' | 'MOCK'
}

export interface BudgetLedger {
  spent_today_usd: string
  remaining_today_usd: string
  spent_month_usd: string
  remaining_month_usd: string
  uncertain_count: number
  warnings: string[]
}

export interface Budget {
  limits: { daily_usd: string; monthly_usd: string; per_job_default_usd: string; warning_threshold: number; max_uncertain_per_job: number }
  timezone: string
  real: BudgetLedger
  mock: BudgetLedger
}

export interface CostSummary {
  period: 'day' | 'month'
  data_origin: 'REAL' | 'MOCK'
  total_usd: string
  call_count: number
  by_model: { provider: string; model: string; cost_usd: string; input_tokens: number; output_tokens: number }[]
  by_job_type: { job_type: string; cost_usd: string; job_count: number }[]
}

export interface Job {
  id: string
  job_type: string
  params: Record<string, unknown>
  status: string
  trigger: string
  data_origin: 'REAL' | 'MOCK'
  schedule_id: string | null
  budget_limit_usd: string | null
  cost_accumulated_usd: string | null
  step_count: number
  ai_call_count: number
  attempt: number
  status_reason_code: string | null
  result: Record<string, unknown> | null
  created_at: string
  started_at: string | null
  finished_at: string | null
}

export interface JobStep {
  seq: number
  name: string
  step_type: string
  status: string
  error_code: string | null
  cost_usd: string | null
  started_at: string | null
  finished_at: string | null
}

export interface Schedule {
  id: string
  name: string
  job_type: string
  cron_expr: string
  timezone: string
  enabled: boolean
  last_run_at: string | null
  next_run_at: string | null
  params: Record<string, unknown>
}

export interface Setting {
  key: string
  value: unknown
  version: number
  updated_at: string
}

export interface Project {
  id: string
  name: string
  target_market: string
  research_language: string
  content_language: string
}

export interface Provider {
  provider: string
  configured: boolean
  key_hint: string | null
  last_check: string | null
}

export interface ModelProfile {
  task_type: string
  provider: string
  model: string
  effort?: string | null
  max_output_tokens?: number | null
}

export function useOverview(includeMock: boolean) {
  return useQuery({
    queryKey: ['dashboard-overview', includeMock],
    queryFn: () => api<Overview>(`/api/v1/dashboard/overview?include_mock=${flag(includeMock)}`),
  })
}

export function useResearchNiches(includeMock: boolean) {
  return useQuery({
    queryKey: ['dashboard-niches', includeMock],
    queryFn: () =>
      api<{ items: ResearchNiche[]; total: number; limit: number }>(`/api/v1/dashboard/niches?include_mock=${flag(includeMock)}`),
  })
}

export function useBudget() {
  return useQuery({ queryKey: ['budget'], queryFn: () => api<Budget>('/api/v1/budget') })
}

export function useCostSummary(period: 'day' | 'month', origin: 'REAL' | 'MOCK') {
  return useQuery({
    queryKey: ['cost-summary', period, origin],
    queryFn: () => api<CostSummary>(`/api/v1/costs/summary?period=${period}&data_origin=${origin}`),
  })
}

export function useJobs(status: string, jobType: string) {
  const q = new URLSearchParams({ page_size: '100' })
  if (status) q.set('status', status)
  if (jobType) q.set('job_type', jobType)
  return useQuery({
    queryKey: ['jobs', status, jobType],
    queryFn: () => api<{ items: Job[]; total: number }>(`/api/v1/jobs?${q.toString()}`),
  })
}

export function useJob(jobId: string) {
  return useQuery({ queryKey: ['job', jobId], queryFn: () => api<Job>(`/api/v1/jobs/${jobId}`) })
}

export function useJobSteps(jobId: string) {
  return useQuery({ queryKey: ['job-steps', jobId], queryFn: () => api<JobStep[]>(`/api/v1/jobs/${jobId}/steps`) })
}

export type JobAction = 'pause' | 'resume' | 'cancel' | 'retry'

export function useJobAction() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ jobId, action }: { jobId: string; action: JobAction }) => api<Job>(`/api/v1/jobs/${jobId}/${action}`, { method: 'POST' }),
    onSettled: () => qc.invalidateQueries({ queryKey: ['jobs'] }).then(() => qc.invalidateQueries({ queryKey: ['job'] })),
  })
}

export function useSchedules() {
  return useQuery({
    queryKey: ['schedules'],
    queryFn: () => api<Schedule[]>('/api/v1/schedules'),
  })
}

export function useScheduleToggle() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) =>
      api<Schedule>(`/api/v1/schedules/${id}`, { method: 'PATCH', body: { enabled } }),
    onSettled: () => qc.invalidateQueries({ queryKey: ['schedules'] }),
  })
}

export function useScheduleDelete() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (id: string) => api<void>(`/api/v1/schedules/${id}`, { method: 'DELETE' }),
    onSettled: () => qc.invalidateQueries({ queryKey: ['schedules'] }),
  })
}

export function useSettings() {
  return useQuery({ queryKey: ['settings'], queryFn: () => api<Setting[]>('/api/v1/settings') })
}

export function useSaveSettings() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (items: { key: string; value: unknown; version: number }[]) =>
      api<Setting[]>('/api/v1/settings', { method: 'PATCH', body: items }),
    onSuccess: (data) => qc.setQueryData(['settings'], data),
  })
}

export function useProject() {
  return useQuery({ queryKey: ['project'], queryFn: () => api<Project>('/api/v1/projects/default') })
}

export function useSaveProject() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: Partial<Pick<Project, 'target_market' | 'research_language' | 'content_language'>>) =>
      api<Project>('/api/v1/projects/default', { method: 'PATCH', body }),
    onSuccess: (data) => qc.setQueryData(['project'], data),
  })
}

export function useSaveBudget() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { daily_usd: string; monthly_usd: string; per_job_default_usd: string; warning_threshold: number }) =>
      api<Budget>('/api/v1/budget', { method: 'PUT', body }),
    onSuccess: (data) => qc.setQueryData(['budget'], data),
  })
}

export function useProviders() {
  return useQuery({
    queryKey: ['providers'],
    queryFn: () => api<Provider[]>('/api/v1/providers'),
  })
}

export function useModelProfiles() {
  return useQuery({
    queryKey: ['model-profiles'],
    queryFn: () => api<ModelProfile[]>('/api/v1/model-profiles'),
  })
}
