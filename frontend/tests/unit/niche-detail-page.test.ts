// T078 – Màn hình 3 "Chi tiết ngách" (FR-026, FR-013e): pain point / persona / bằng chứng + nguồn, trạng thái đang tải / rỗng /
// lỗi, nhãn MOCK, UNKNOWN hiển thị rõ, nút xóa bằng chứng có bước xác nhận. Test case: TC_E1_FR026_02.
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { beforeAll, describe, expect, it } from 'vitest'
import type { NicheDetail } from '../../src/api/types'
import i18n from '../../src/i18n'
import { NicheDetailView } from '../../src/pages/discovery/NicheDetailView'

const UNKNOWN = { value: null, status: 'UNKNOWN' as const, evidence_ids: [] }
const niche: NicheDetail = {
  id: 'n1',
  name: '[MOCK] Small bakery inventory',
  micro_niche: '[MOCK] Flour alerts',
  country: 'US',
  customer_group: 'owners of micro bakeries',
  core_problem: 'running out of ingredients',
  opportunity_score: null,
  confidence_score: null,
  evidence_status: 'INSUFFICIENT_EVIDENCE',
  monetization_status: 'MONETIZATION_UNVERIFIED',
  risk_flags: ['MONETIZATION_RISK'],
  ai_recommendation: 'UNKNOWN',
  decision_status: 'CANDIDATE',
  data_origin: 'MOCK',
  disclaimer_key: 'discovery.disclaimer.evidence_not_profitability',
  pain_points: [
    { id: 'p1', title: '[MOCK] Stock runs out', description: 'd', severity: 4, evidence_count: 2, status: 'VERIFIED' },
  ],
  persona: {
    segment: { value: '[MOCK] micro bakery owners', status: 'VERIFIED', evidence_ids: ['e1'] },
    context: UNKNOWN,
    goals: UNKNOWN,
    obstacles: UNKNOWN,
    ability_to_pay: {
      value: [
        { value: '[MOCK] small fee ok', evidence_ids: ['e1'] },
        { value: '[MOCK] too expensive', evidence_ids: ['e2'] },
      ],
      status: 'CONFLICTING',
      evidence_ids: ['e1', 'e2'],
    },
  },
  findings: {
    CURRENT_SOLUTIONS: { value: ['[MOCK] spreadsheets'], status: 'VERIFIED', evidence_ids: ['e1'] },
    MARKET_GAPS: UNKNOWN,
    POTENTIAL_PRODUCTS: UNKNOWN,
    MONETIZATION: UNKNOWN,
    CHANNELS: UNKNOWN,
    RISKS: UNKNOWN,
  },
  competitors: [{ name: '[MOCK] Spreadsheet', kind: 'MANUAL_WORKAROUND', url: null, strengths: [], weaknesses: ['slow'] }],
  evidence: [
    {
      id: 'e1',
      source_url: 'https://forum.example/t/1',
      source_domain: 'forum.example',
      excerpt: 'Email [EMAIL] if you found a fix',
      collected_at: '2026-11-20T06:00:00Z',
      verification_status: 'VERIFIED',
      redaction_status: 'REDACTED',
      purpose: 'PAIN_POINT',
      relevance: 0.9,
      quality: 0.8,
      independence_group: 'domain:forum.example',
      counted_for_threshold: true,
      policy_verified_at: '2026-11-01',
      data_origin: 'MOCK',
    },
  ],
  latest_evaluation: {
    id: 'ev1',
    run_id: 'r1',
    weights_version: 1,
    criteria: {
      problem_severity: { score: 75, status: 'VERIFIED', weight: 25, normalized_weight: 0.357, reason: '[MOCK] weekly losses', evidence_ids: ['e1'] },
      monetization: { score: null, status: 'UNKNOWN', weight: 20, normalized_weight: null, reason: '', evidence_ids: [] },
    },
    coverage: 70,
    scoring_status: 'SCORED',
    opportunity_score: 60.71,
    confidence_score: 30,
    confidence_components: {},
    missing_data: ['monetization'],
    computed_without_ai: false,
    data_origin: 'MOCK',
    created_at: '2026-11-20T06:00:00Z',
  },
  run_ids: ['r1'],
}

const noop = () => undefined
const render = (props: Partial<Parameters<typeof NicheDetailView>[0]>) =>
  renderToStaticMarkup(
    createElement(NicheDetailView, {
      state: 'ready',
      niche,
      erasing: false,
      eraseError: null,
      confirmEvidenceId: null,
      onAskErase: noop,
      onConfirmErase: noop,
      onCancelErase: noop,
      onRetry: noop,
      ...props,
    }),
  )

describe('TC_E1_FR026_02 màn hình chi tiết ngách', () => {
  beforeAll(async () => {
    await i18n.changeLanguage('vi')
  })

  it('hiển thị đang tải, lỗi, không tìm thấy', () => {
    expect(render({ state: 'loading', niche: undefined })).toContain('Đang tải…')
    expect(render({ state: 'error', niche: undefined, errorCode: 'ERASURE_LEDGER_NOT_APPLIED' })).toContain(
      'Sổ xóa bằng chứng chưa được áp dụng',
    )
    expect(render({ state: 'error', niche: undefined, errorCode: 'NICHE_NOT_FOUND' })).toContain('Không tìm thấy ngách')
  })

  it('hiển thị pain point, persona, bằng chứng + nguồn, nhãn MOCK và trạng thái bằng chứng', () => {
    const html = render({})
    expect(html).toContain('data-testid="mock-badge"')
    expect(html).toContain('[MOCK] Stock runs out')
    expect(html).toContain('Chưa đủ bằng chứng')
    expect(html).toContain('Chưa xác minh khả năng kiếm tiền')
    expect(html).toContain('[MOCK] micro bakery owners')
    expect(html).toContain('Mâu thuẫn') // CONFLICTING hiển thị mọi giá trị
    expect(html).toContain('[MOCK] small fee ok')
    expect(html).toContain('[MOCK] too expensive')
    expect(html).toContain('UNKNOWN')
    expect(html).toContain('https://forum.example/t/1')
    expect(html).toContain('Email [EMAIL] if you found a fix')
    expect(html).toContain('2026-11-01') // ngày xác minh nguồn ALLOWED
    expect(html).toContain('đạt ngưỡng bằng chứng không có nghĩa là ngách sinh lợi')
    expect(html).toContain('data-testid="scoring"')
    expect(html).toContain('60.71')
    expect(html).toContain('[MOCK] weekly losses')
    expect(html).toContain('không phải dự báo doanh thu')
  })

  it('rỗng: không có bằng chứng / pain point', () => {
    const html = render({ niche: { ...niche, evidence: [], pain_points: [], competitors: [] } })
    expect(html).toContain('Chưa có bằng chứng')
    expect(html).toContain('Chưa có pain point')
  })

  it('xóa bằng chứng cần xác nhận', () => {
    expect(render({})).toContain('data-testid="erase-e1"')
    const confirm = render({ confirmEvidenceId: 'e1' })
    expect(confirm).toContain('data-testid="erase-confirm"')
    expect(confirm).toContain('không thể hoàn tác')
    expect(render({ eraseError: 'EVIDENCE_ALREADY_ERASED' })).toContain('Bằng chứng này đã bị xóa trước đó')
  })

  it('chuyển tiếng Anh', async () => {
    await i18n.changeLanguage('en')
    expect(render({})).toContain('Pain points')
    await i18n.changeLanguage('vi')
  })
})
