// T009 – trang E4 (FR-001…FR-018, FR-021, SC-001, SC-004): menu, Tổng quan, Sản phẩm/Keyword toàn cục, Agent Jobs, Chi phí, Cài đặt, VI/EN.
// Test case: TC_E4_FR005_01, TC_E4_FR006_03, TC_E4_FR008_02, TC_E4_FR010_02, TC_E4_FR011_02, TC_E4_FR012_02, TC_E4_FR013_01,
// TC_E4_FR014_01, TC_E4_FR015_01, TC_E4_FR016_01, TC_E4_FR017_01, TC_E4_FR018_01, TC_E4_FR004_01, TC_E4_FR003_01, TC_E4_FR001_01,
// TC_E4_FR002_01, TC_E4_SC001_01, TC_E4_SC004_01, TC_E4_FR021_01.
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router'
import { beforeAll, describe, expect, it } from 'vitest'
import type { Budget, CostSummary, Job, Overview, ResearchNiche } from '../../src/api/dashboard'
import { MainNav } from '../../src/app/Layout'
import { NAV_ITEMS } from '../../src/app/nav'
import { routes } from '../../src/app/routes'
import i18n, { formatMoney, formatNumber, formatPercent } from '../../src/i18n'
import en from '../../src/i18n/locales/en.json'
import vi from '../../src/i18n/locales/vi.json'
import { allowedActions } from '../../src/lib/jobs'
import { CostsView } from '../../src/pages/dashboard/CostsView'
import { JobDetailView } from '../../src/pages/dashboard/JobDetailView'
import { JobsView } from '../../src/pages/dashboard/JobsView'
import { OverviewView } from '../../src/pages/dashboard/OverviewView'
import { ResearchNichesView } from '../../src/pages/dashboard/ResearchNichesView'
import { SettingsView } from '../../src/pages/dashboard/SettingsView'

const noop = () => undefined
const wrap = (el: ReturnType<typeof createElement>) => renderToStaticMarkup(createElement(MemoryRouter, null, el))

const overview: Overview = {
  niches: { total: 3, by_evidence_status: { EVIDENCE_SUFFICIENT: 2 }, by_decision: { CANDIDATE: 3 } },
  products: { total: 2, ready_to_promote: 1 },
  keywords: { total: 12, clusters: 6, long_tail: 7 },
  jobs: { by_status: { RUNNING: 1, QUEUED: 1 }, failed_7d: 2 },
  top_niches: [{ niche_id: 'n1', name: '[MOCK DEMO] Bakery', opportunity_score: 72.5, confidence_score: 61, data_origin: 'MOCK' }],
  include_mock: true,
  generated_at: '2026-11-28T00:00:00Z',
}
const ledger = { spent_today_usd: '0.000000', remaining_today_usd: '3.000000', spent_month_usd: '1.500000', remaining_month_usd: '28.5', uncertain_count: 0, warnings: [] as string[] }
const budget: Budget = {
  limits: { daily_usd: '3.000000', monthly_usd: '30.000000', per_job_default_usd: '2.000000', warning_threshold: 0.8, max_uncertain_per_job: 3 },
  timezone: 'Asia/Ho_Chi_Minh',
  real: { ...ledger, warnings: ['MONTHLY_80'] },
  mock: { ...ledger, spent_month_usd: '0.004000' },
}
const niche = (over: Partial<ResearchNiche>): ResearchNiche => ({
  niche_id: 'n1',
  name: '[MOCK DEMO] Bakery',
  country: 'US',
  evidence_status: 'EVIDENCE_SUFFICIENT',
  decision_status: 'CANDIDATE',
  eligible: true,
  opportunity_score: 72.5,
  confidence_score: 61,
  products: { has_run: true, total: 2, ready_to_promote: 1 },
  keywords: { has_run: true, total: 12, clusters: 6, long_tail: 7, best_cluster: { cluster_id: 'c1', name: 'flour alerts', opportunity_score: 71.25, confidence_score: 40 } },
  data_origin: 'MOCK',
  ...over,
})
const job = (status: string): Job => ({
  id: `j-${status}`,
  job_type: 'keywords.run',
  params: { niche_id: 'n1' },
  status,
  trigger: 'MANUAL',
  data_origin: 'MOCK',
  schedule_id: null,
  budget_limit_usd: '2.000000',
  cost_accumulated_usd: '0.002000',
  step_count: 3,
  ai_call_count: 2,
  attempt: 1,
  status_reason_code: status === 'FAILED' ? 'PROVIDER_TIMEOUT' : null,
  result: null,
  created_at: '2026-11-28T00:00:00Z',
  started_at: null,
  finished_at: null,
})
const cost = (origin: 'REAL' | 'MOCK', total: string): CostSummary => ({
  period: 'month',
  data_origin: origin,
  total_usd: total,
  call_count: origin === 'MOCK' ? 4 : 0,
  by_model: origin === 'MOCK' ? [{ provider: 'mock', model: 'mock-model', cost_usd: total, input_tokens: 2000, output_tokens: 800 }] : [],
  by_job_type: [],
})

beforeAll(async () => {
  await i18n.changeLanguage('vi')
})

describe('TC_E4_FR005_01 menu điều hướng', () => {
  it('9 mục, đánh dấu trang hiện tại', () => {
    const html = wrap(createElement(MainNav, { pathname: '/niches/n1/keywords/c1' }))
    for (const label of ['Tổng quan', 'Ngách', 'Sản phẩm', 'Keyword', 'Agent jobs', 'Chi phí', 'Cài đặt', 'Nguồn dữ liệu', 'Trạng thái']) {
      expect(html).toContain(label)
    }
    expect(NAV_ITEMS).toHaveLength(9)
    expect(html.match(/aria-current="page"/g)).toHaveLength(1)
    expect(html).toMatch(/aria-current="page"[^>]*data-testid="nav-keywords"|data-testid="nav-keywords"[^>]*aria-current/)
  })

  it('TC_E4_FR021_01 không có route Content Calendar/Revenue (Later)', () => {
    const paths = routes.map((r) => r.path ?? '')
    expect(paths).toEqual(expect.arrayContaining(['/overview', '/products', '/keywords', '/jobs', '/jobs/:jobId', '/costs', '/settings']))
    expect(paths.some((p) => /calendar|revenue/i.test(p))).toBe(false)
  })
})

describe('TC_E4_FR006_03 Tổng quan', () => {
  const render = (p: Partial<Parameters<typeof OverviewView>[0]>) =>
    wrap(createElement(OverviewView, { state: 'ready', data: overview, budget, includeMock: true, onIncludeMockChange: noop, onRetry: noop, ...p }))

  it('số liệu, chi phí REAL/MOCK, ngách hàng đầu kèm Confidence (TC_E4_FR012_02)', () => {
    const html = render({})
    expect(html).toContain('2 · 1 sẵn sàng')
    expect(html).toContain('12 · 6 cluster')
    expect(html).toContain('2 đang chạy · 2 lỗi (7 ngày)')
    expect(html).toContain('không tính vào chi phí thực')
    expect(html).toContain('Confidence: 61')
    expect(html).toContain('href="/niches/n1"')
    expect(html).toContain('data-testid="mock-badge"')
  })

  it('TC_E4_FR008_02 TC_E4_SC004_01 rỗng/lỗi/đang tải', () => {
    const empty = render({ data: { ...overview, niches: { total: 0, by_evidence_status: {}, by_decision: {} }, top_niches: [] } })
    expect(empty).toContain('data-testid="empty-state"')
    expect(empty).toContain('Bắt đầu khám phá ngách')
    expect(render({ state: 'error', errorCode: 'ERASURE_LEDGER_NOT_APPLIED' })).toContain('data-testid="load-error"')
    expect(render({ state: 'loading' })).toContain('Đang tải…')
  })
})

describe('TC_E4_FR010_02 TC_E4_FR011_02 trang toàn cục', () => {
  const render = (mode: 'products' | 'keywords', items: ResearchNiche[]) =>
    wrap(createElement(ResearchNichesView, { mode, state: 'ready', items, includeMock: true, onIncludeMockChange: noop, onRetry: noop }))

  it('sản phẩm: tóm tắt + liên kết; chưa chạy hiển thị "chưa có", không phải 0', () => {
    const html = render('products', [niche({}), niche({ niche_id: 'n2', name: 'Other', products: { has_run: false, total: 0, ready_to_promote: 0 } })])
    expect(html).toContain('2 sản phẩm · 1 sẵn sàng affiliate')
    expect(html).toContain('href="/niches/n1/products"')
    expect(html).toContain('Chưa tìm sản phẩm')
    expect(html).not.toContain('0 sản phẩm')
  })

  it('keyword: cluster tốt nhất kèm Confidence; ngách không đủ điều kiện và chưa chạy bị ẩn', () => {
    const html = render('keywords', [niche({}), niche({ niche_id: 'n3', name: 'Hidden', eligible: false, keywords: { has_run: false, total: 0, clusters: 0, long_tail: 0, best_cluster: null } })])
    expect(html).toContain('12 keyword · 6 cluster · 7 long-tail')
    expect(html).toContain('flour alerts')
    expect(html).toContain('Confidence: 40')
    expect(html).not.toContain('Hidden')
    expect(render('keywords', [])).toContain('Chưa có ngách đủ điều kiện')
  })
})

describe('TC_E4_FR013_01 TC_E4_FR014_01 TC_E4_FR015_01 Agent Jobs', () => {
  it('thao tác hợp lệ theo trạng thái', () => {
    expect(allowedActions('RUNNING')).toEqual(['pause', 'cancel'])
    expect(allowedActions('PAUSED_BUDGET')).toEqual(['resume', 'cancel'])
    expect(allowedActions('FAILED')).toEqual(['retry'])
    expect(allowedActions('SUCCEEDED')).toEqual([])
  })

  it('danh sách, lọc, lịch chạy, hủy có xác nhận', () => {
    const calls: string[] = []
    const html = wrap(
      createElement(JobsView, {
        state: 'ready',
        jobs: [job('RUNNING'), job('FAILED')],
        total: 5,
        status: '',
        jobType: '',
        jobTypes: ['keywords.run'],
        schedules: [{ id: 's1', name: 'weekly', job_type: 'keywords.serp_check', cron_expr: '0 3 * * 1', timezone: 'UTC', enabled: true, last_run_at: null, next_run_at: null, params: {} }],
        actionError: null,
        onStatusChange: noop,
        onJobTypeChange: noop,
        onAction: (id: string, a: string) => calls.push(`${id}:${a}`),
        onToggleSchedule: noop,
        onDeleteSchedule: noop,
        onRetry: noop,
        confirm: () => false,
      }),
    )
    expect(html).toContain('Đang chạy')
    expect(html).toContain('data-testid="job-pause"')
    expect(html).toContain('data-testid="job-retry"')
    expect(html).toContain('Hiển thị 2/5 job mới nhất')
    expect(html).toContain('weekly')
    expect(html).toContain('0 3 * * 1')
    expect(html).toContain('href="/jobs/j-RUNNING"')
  })

  it('chi tiết: mã lỗi thân thiện, không stack trace', () => {
    const html = wrap(
      createElement(JobDetailView, {
        state: 'ready',
        job: job('FAILED'),
        steps: [{ seq: 1, name: 'preflight', step_type: 'LOGIC', status: 'FAILED', error_code: 'PROVIDER_TIMEOUT', cost_usd: null, started_at: null, finished_at: null }],
        actionError: null,
        onAction: noop,
        onRetry: noop,
      }),
    )
    expect(html).toContain('data-testid="job-reason"')
    expect(html).toContain('preflight')
    expect(html).not.toMatch(/Traceback|at Object\./)
  })
})

describe('TC_E4_FR016_01 Chi phí', () => {
  it('REAL và MOCK tách riêng, cảnh báo ngân sách', () => {
    const html = wrap(
      createElement(CostsView, { state: 'ready', budget, real: cost('REAL', '0.000000'), mock: cost('MOCK', '0.004000'), period: 'month', onPeriodChange: noop, onRetry: noop }),
    )
    expect(html).toContain('data-testid="costs-real"')
    expect(html).toContain('data-testid="costs-mock"')
    expect(html).toContain('Chưa có chi phí trong kỳ')
    expect(html).toContain('mock-model')
    expect(html).toContain('không phải chi phí thực')
    expect(html).toContain('ngưỡng cảnh báo ngân sách tháng')
  })
})

describe('TC_E4_FR017_01 TC_E4_FR018_01 TC_E4_FR004_01 Cài đặt', () => {
  const props = {
    state: 'ready' as const,
    settings: [
      { key: 'system.timezone', value: 'Asia/Ho_Chi_Minh', version: 1, updated_at: '' },
      { key: 'ui.default_locale', value: 'vi', version: 1, updated_at: '' },
      { key: 'agent.default_max_steps', value: 20, version: 1, updated_at: '' },
    ],
    project: { id: 'p', name: 'Default', target_market: 'US', research_language: 'auto', content_language: 'en' },
    budget,
    providers: [{ provider: 'anthropic', configured: false, key_hint: null, last_check: null }],
    profiles: [{ task_type: 'keywords.generate', provider: 'anthropic', model: 'claude-haiku-5-5' }],
    paidCallsEnabled: false,
    saved: null,
    error: null,
    onSaveSettings: noop,
    onSaveProject: noop,
    onSaveBudget: noop,
    onRetry: noop,
  }

  it('form cấu hình không bí mật; ngôn ngữ nội dung tách giao diện', () => {
    const html = wrap(createElement(SettingsView, props))
    expect(html).toContain('Ngôn ngữ giao diện mặc định')
    expect(html).toContain('Ngôn ngữ nội dung')
    expect(html).toContain('độc lập với ngôn ngữ giao diện')
    expect(html).toContain('value="Asia/Ho_Chi_Minh"')
    expect(html).toContain('data-testid="save-budget"')
  })

  it('AI provider/model chỉ đọc: không có nút xác minh/kiểm tra kết nối/bật có phí', () => {
    const html = wrap(createElement(SettingsView, props))
    expect(html).toContain('claude-haiku-5-5')
    expect(html).toContain('TẮT')
    const ai = html.slice(html.indexOf('data-testid="ai-readonly"'))
    expect(ai).not.toMatch(/<button|<input/)
  })

  it('lỗi validate hiển thị theo trường', () => {
    const html = wrap(
      createElement(SettingsView, { ...props, error: { code: 'VALIDATION_ERROR', fields: [{ field: 'per_job_default_usd', code: 'per_job_le_daily_le_monthly' }] } }),
    )
    expect(html).toContain('data-testid="field-error-per_job_default_usd"')
    expect(html).toContain('mỗi job ≤ ngày ≤ tháng')
  })
})

describe('TC_E4_FR003_01 định dạng locale', () => {
  it('số, tiền, phần trăm theo VI/EN', () => {
    expect(formatNumber(1234.5, 'vi')).toBe('1.234,5')
    expect(formatNumber(1234.5, 'en')).toBe('1,234.5')
    expect(formatMoney('1.5', 'en')).toBe('$1.50')
    expect(formatMoney('0.004', 'vi')).toContain('0,004')
    expect(formatPercent(0.8, 'en')).toBe('80%')
  })
})

describe('TC_E4_FR001_01 TC_E4_FR002_01 TC_E4_SC001_01 song ngữ', () => {
  it('khóa dashboard và nav có ở cả VI và EN', () => {
    const keys = (o: object, p = ''): string[] =>
      Object.entries(o).flatMap(([k, v]) => (typeof v === 'object' ? keys(v as object, `${p}${k}.`) : [`${p}${k}`]))
    const v = vi as Record<string, object>
    const e = en as Record<string, object>
    expect(keys(e.dashboard).sort()).toEqual(keys(v.dashboard).sort())
    expect(keys(e.nav).sort()).toEqual(keys(v.nav).sort())
  })

  it('chuyển tiếng Anh', async () => {
    await i18n.changeLanguage('en')
    expect(wrap(createElement(MainNav, { pathname: '/overview' }))).toContain('Overview')
    expect(
      wrap(createElement(OverviewView, { state: 'ready', data: overview, budget, includeMock: true, onIncludeMockChange: noop, onRetry: noop })),
    ).toContain('2 running · 2 failed (7 days)')
    await i18n.changeLanguage('vi')
  })
})
