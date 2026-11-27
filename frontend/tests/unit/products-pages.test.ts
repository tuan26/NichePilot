// T050 – Màn hình E2 (FR-036, SC-006): danh sách sản phẩm (2 tab, MOCK, readiness, Coverage + còn thiếu, chú thích) và chi tiết
// (thuộc tính + trạng thái + nguồn, CONFLICTING đủ giá trị, chương trình, quyết định, cảnh báo đổi điều khoản), VI/EN.
// Test case: TC_E2_FR036_01, TC_E2_FR036_02, TC_E2_FR036_03.
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router'
import { beforeAll, describe, expect, it } from 'vitest'
import type { ProductDetail, ProductItem } from '../../src/api/types'
import i18n from '../../src/i18n'
import en from '../../src/i18n/locales/en.json'
import vi from '../../src/i18n/locales/vi.json'
import { NicheProductsView } from '../../src/pages/products/NicheProductsView'
import { ProductDetailView } from '../../src/pages/products/ProductDetailView'

const noop = () => undefined
const item: ProductItem = {
  product_id: 'p1',
  name: '[MOCK] StockPal',
  vendor: null,
  official_domain: 'stockpal.example',
  category: 'SOFTWARE',
  readiness_status: 'READY_TO_PROMOTE',
  risk_flags: [],
  evaluation: {
    opportunity_score: 88.24,
    confidence_score: 80,
    coverage: 85,
    scoring_status: 'SCORED',
    criteria: { fit: { level: 75, status: 'INFERRED', reason: '[MOCK]', evidence_ids: ['e1'] } },
    missing: ['price_fit'],
    weights_version: 1,
    computed_at: '2026-11-27T00:00:00Z',
  },
  ai_recommendation: 'SELECT',
  ai_recommendation_reason: '[MOCK] fits',
  decision_status: 'CANDIDATE',
  decision_reason: null,
  persona_match: 'MATCH',
  data_origin: 'MOCK',
}
const detail: ProductDetail = {
  ...item,
  attributes: [
    {
      key: 'price',
      status: 'VERIFIED',
      value: [{ plan: 'Starter', amount: 19 }],
      flags: [],
      values: [
        {
          value: { plan: 'Starter', amount: 19 },
          status: 'VERIFIED',
          evidence_id: 'e2',
          source_url: 'https://stockpal.example/pricing',
          excerpt: '[MOCK] $19 per month',
          collected_at: '2026-11-27T00:00:00Z',
          verified_at: '2026-11-27T00:00:00Z',
        },
      ],
    },
  ],
  pain_points: [{ pain_point_id: 'pp1', title: '[MOCK] Ingredients run out', evidence: [] }],
  programs: [
    {
      program_id: 'g1',
      name: '[MOCK] StockPal Partners',
      operator_type: 'VENDOR',
      operator_name: null,
      operator_domain: 'stockpal.example',
      terms_url: 'https://stockpal.example/partners',
      verification_status: 'VERIFIED',
      attributes: [
        {
          key: 'commission',
          status: 'CONFLICTING',
          value: { kind: 'percent', value: 30 },
          flags: ['THIRD_PARTY_DISAGREES'],
          values: [
            { value: { kind: 'percent', value: 30 }, status: 'VERIFIED', evidence_id: 'e3', source_url: 'https://stockpal.example/partners', excerpt: '', collected_at: null, verified_at: null },
            { value: { kind: 'percent', value: 25 }, status: 'INFERRED', evidence_id: 'e4', source_url: 'https://blog.example/x', excerpt: '', collected_at: null, verified_at: null },
          ],
        },
        { key: 'vn_eligibility', status: 'UNKNOWN', value: null, flags: [], values: [] },
      ],
      watch_enabled: true,
      last_checked_at: '2026-11-27T00:00:00Z',
      last_check_error: null,
      terms_versions: [{ version: 2, checked_at: '2026-11-27T00:00:00Z', changes: [{ claim_key: 'commission', old: 30, new: 20 }], acknowledged_at: null }],
      data_origin: 'MOCK',
    },
  ],
  disclaimer_key: 'products.opportunity.disclaimer',
}

const renderList = (props: Partial<Parameters<typeof NicheProductsView>[0]>) =>
  renderToStaticMarkup(
    createElement(
      MemoryRouter,
      null,
      createElement(NicheProductsView, {
        nicheId: 'n1',
        list: 'ranked',
        state: 'ready',
        items: [],
        includeMock: false,
        running: false,
        runError: null,
        runStarted: false,
        onListChange: noop,
        onIncludeMockChange: noop,
        onRun: noop,
        onRetry: noop,
        ...props,
      }),
    ),
  )
const renderDetail = (props: Partial<Parameters<typeof ProductDetailView>[0]>) =>
  renderToStaticMarkup(
    createElement(
      MemoryRouter,
      null,
      createElement(ProductDetailView, {
        nicheId: 'n1',
        state: 'ready',
        product: detail,
        decisionError: null,
        onDecision: noop,
        onWatch: noop,
        onAcknowledge: noop,
        onRetry: noop,
        ...props,
      }),
    ),
  )

describe('TC_E2_FR036_01 danh sách sản phẩm', () => {
  beforeAll(async () => {
    await i18n.changeLanguage('vi')
  })

  it('2 tab, chú thích, rỗng/lỗi', () => {
    const html = renderList({})
    expect(html).toContain('Xếp hạng sản phẩm')
    expect(html).toContain('Cần nghiên cứu thêm')
    expect(html).toContain('không phải dự báo doanh thu')
    expect(html).toContain('Chưa có sản phẩm nào')
    expect(renderList({ state: 'error', errorCode: 'NICHE_NOT_ELIGIBLE' })).toContain('chưa đủ điều kiện tìm sản phẩm')
    expect(renderList({ runError: 'NO_COMPLIANT_SEARCH_SOURCE' })).toContain('data-testid="run-error"')
  })

  it('điểm, Coverage, còn thiếu, readiness, MOCK', () => {
    const html = renderList({ items: [item] })
    expect(html).toContain('88.24')
    expect(html).toContain('85%')
    expect(html).toContain('Đủ điều kiện tham gia')
    expect(html).toContain('Còn thiếu: Giá phù hợp khả năng chi trả')
    expect(html).toContain('data-testid="mock-badge"')
    expect(html).toContain('href="/niches/n1/products/p1"')
  })
})

describe('TC_E2_FR036_02 chi tiết sản phẩm', () => {
  it('thuộc tính + trạng thái + nguồn, CONFLICTING đủ giá trị, UNKNOWN rõ ràng', () => {
    const html = renderDetail({})
    expect(html).toContain('https://stockpal.example/pricing')
    expect(html).toContain('data-status="CONFLICTING"')
    expect(html).toContain('value: 30')
    expect(html).toContain('value: 25')
    expect(html).toContain('Đăng ký từ Việt Nam')
    expect(html).toContain('UNKNOWN')
  })

  it('chương trình, cảnh báo đổi điều khoản, quyết định, không đăng ký thay', () => {
    const html = renderDetail({})
    expect(html).toContain('Điều khoản đã thay đổi (phiên bản 2)')
    expect(html).toContain('Ghi quyết định')
    expect(html).toContain('Nên chọn')
    expect(html).toContain('không đăng ký tài khoản')
    expect(renderDetail({ state: 'loading' })).toContain('Đang tải…')
  })
})

describe('TC_E2_FR036_03 TC_E2_SC006_01 song ngữ', () => {
  it('khóa products có ở cả VI và EN', () => {
    const keys = (o: object, p = ''): string[] =>
      Object.entries(o).flatMap(([k, v]) => (typeof v === 'object' ? keys(v as object, `${p}${k}.`) : [`${p}${k}`]))
    expect(keys((en as Record<string, object>).products).sort()).toEqual(keys((vi as Record<string, object>).products).sort())
  })

  it('chuyển tiếng Anh', async () => {
    await i18n.changeLanguage('en')
    expect(renderList({ items: [item] })).toContain('Eligible to join')
    expect(renderDetail({})).toContain('Terms changed (version 2)')
    await i18n.changeLanguage('vi')
  })
})
