// T091 – Màn hình 2 "Bảng xếp hạng ngách" (FR-026, FR-019c): 3 tab, Opportunity/Confidence/Coverage, trạng thái xác minh,
// Monetization, chú thích "không phải dự báo doanh thu", đang tải/rỗng/lỗi, nhãn MOCK. Test case: TC_E1_FR026_03.
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router'
import { beforeAll, describe, expect, it } from 'vitest'
import type { NicheSummary } from '../../src/api/types'
import i18n from '../../src/i18n'
import { NicheRankingView } from '../../src/pages/discovery/NicheRankingView'

const item: NicheSummary = {
  id: 'n1',
  name: '[MOCK] Small bakery inventory',
  micro_niche: 'Flour alerts',
  country: 'US',
  opportunity_score: 60.71,
  confidence_score: 54.2,
  coverage: 70,
  scoring_status: 'SCORED',
  evidence_status: 'EVIDENCE_SUFFICIENT',
  verification_summary: { VERIFIED: 1, INFERRED: 3, UNKNOWN: 2, CONFLICTING: 0 },
  monetization_status: 'MONETIZATION_UNVERIFIED',
  risk_flags: ['MONETIZATION_RISK'],
  ai_recommendation: 'PURSUE',
  decision_status: 'CANDIDATE',
  has_possible_duplicate: false,
  data_origin: 'MOCK',
}

const noop = () => undefined
const render = (props: Partial<Parameters<typeof NicheRankingView>[0]>) =>
  renderToStaticMarkup(
    createElement(
      MemoryRouter,
      null,
      createElement(NicheRankingView, {
      list: 'research',
      state: 'ready',
      items: [],
      includeMock: false,
      onListChange: noop,
      onIncludeMockChange: noop,
      onRetry: noop,
      ...props,
      }),
    ),
  )

describe('TC_E1_FR026_03 màn hình bảng xếp hạng', () => {
  beforeAll(async () => {
    await i18n.changeLanguage('vi')
  })

  it('có 3 tab và chú thích Opportunity', () => {
    const html = render({})
    expect(html).toContain('Cơ hội nghiên cứu')
    expect(html).toContain('Ưu tiên affiliate')
    expect(html).toContain('Cần nghiên cứu thêm')
    expect(html).toContain('không phải dự báo doanh thu')
  })

  it('đang tải, rỗng, lỗi', () => {
    expect(render({ state: 'loading' })).toContain('Đang tải…')
    expect(render({ items: [] })).toContain('Chưa có ngách nào')
    expect(render({ state: 'error', errorCode: 'ERASURE_LEDGER_NOT_APPLIED' })).toContain('Sổ xóa bằng chứng chưa được áp dụng')
  })

  it('hiển thị điểm, Coverage, trạng thái xác minh, Monetization, MOCK', () => {
    const html = render({ items: [item] })
    expect(html).toContain('60.71')
    expect(html).toContain('54.2')
    expect(html).toContain('70%')
    expect(html).toContain('Chưa xác minh khả năng kiếm tiền')
    expect(html).toContain('data-testid="mock-badge"')
    expect(html).toContain('href="/niches/n1"')
    expect(html).toContain('UNKNOWN: 2')
  })

  it('INSUFFICIENT_SCORING_DATA không có Opportunity', () => {
    const html = render({
      list: 'needs_research',
      items: [{ ...item, opportunity_score: null, scoring_status: 'INSUFFICIENT_SCORING_DATA', coverage: 45 }],
    })
    expect(html).toContain('Chưa đủ dữ liệu chấm điểm')
  })

  it('chuyển tiếng Anh', async () => {
    await i18n.changeLanguage('en')
    expect(render({})).toContain('Research opportunities')
    await i18n.changeLanguage('vi')
  })
})
