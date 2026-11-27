// T035 – Màn hình E3 (FR-028, SC-006): danh sách cluster (2 tab, MOCK, điểm, chú thích) và chi tiết cluster (keyword + chỉ số UNKNOWN,
// intent, SERP, gap, kênh, persona, strategy, quyết định, cảnh báo SERP), VI/EN.
// Test case: TC_E3_FR028_03, TC_E3_FR009_04, TC_E3_SC006_01.
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { MemoryRouter } from 'react-router'
import { beforeAll, describe, expect, it } from 'vitest'
import type { ClusterDetail, ClusterItem, KeywordMetric } from '../../src/api/types'
import i18n from '../../src/i18n'
import en from '../../src/i18n/locales/en.json'
import vi from '../../src/i18n/locales/vi.json'
import { KeywordClusterView } from '../../src/pages/keywords/KeywordClusterView'
import { NicheKeywordsView } from '../../src/pages/keywords/NicheKeywordsView'

const noop = () => undefined
const unknown: KeywordMetric = { value: null, source: null, collected_at: null, market: null }
const item: ClusterItem = {
  cluster_id: 'c1',
  niche_id: 'n1',
  name: 'how to stop running out of ingredients in a micro bakery',
  intent: 'INFORMATIONAL',
  keyword_count: 3,
  long_tail_count: 2,
  opportunity_score: 71.25,
  confidence_score: 92,
  scored_count: 3,
  origin_label: '[MOCK] Ingredients run out',
  decision_status: 'CANDIDATE',
  serp_alert: false,
  data_origin: 'MOCK',
}
const detail: ClusterDetail = {
  ...item,
  serp_alert: true,
  keywords: [
    {
      keyword_id: 'k1',
      cluster_id: 'c1',
      text: 'how to stop running out of ingredients in a micro bakery',
      language: 'en',
      market: 'US',
      keyword_type: 'PROBLEM',
      length_class: 'LONG_TAIL',
      intent: 'INFORMATIONAL',
      intent_status: 'VERIFIED',
      intent_reason: '[MOCK]',
      risk_flags: ['BRAND_TERM'],
      origins: [{ origin_type: 'PAIN_POINT', ref_id: 'pp1', label: '[MOCK] Ingredients run out', reason: null }],
      metrics: { search_volume: unknown, cpc: unknown, keyword_difficulty: unknown },
      evaluation: {
        opportunity_score: 71.25,
        confidence_score: 92,
        coverage: 100,
        scoring_status: 'SCORED',
        criteria: {},
        missing: ['content_gap'],
        weights_version: 1,
        computed_at: '2026-11-27T00:00:00Z',
      },
      data_origin: 'MOCK',
    },
  ],
  serp: [
    {
      keyword_id: 'k1',
      version: 2,
      collected_at: '2026-11-27T00:00:00Z',
      results: [{ position: 1, url: 'https://bakersforum.example/t/1', domain: 'bakersforum.example', title: null, page_type: 'forum' }],
      changes: { added: ['https://bakersforum.example/t/1'] },
      acknowledged_at: null,
    },
  ],
  competitor_pages: [],
  content_gaps: { status: 'OBSERVED', items: [{ pain_point_id: 'pp2', title: '[MOCK] Too pricey', checked_urls: ['u1', 'u2'] }] },
  channels: { status: 'OBSERVED', items: [{ domain: 'bakersforum.example', kind: 'forum', evidence_urls: ['https://bakersforum.example/t/1'] }] },
  persona: {
    goals: { status: 'INFERRED', value: '[MOCK] never run out', evidence_ids: ['e1'] },
    barriers: { status: 'UNKNOWN', value: null, evidence_ids: [] },
  },
  strategy: { status: 'INFERRED', content_type: 'GUIDE', angle: '[MOCK] step-by-step low-stock routine' },
  decision_reason: null,
  watch_enabled: true,
  last_checked_at: null,
  last_check_error: null,
  disclaimer_key: 'keywords.opportunity.disclaimer',
}

const renderList = (props: Partial<Parameters<typeof NicheKeywordsView>[0]>) =>
  renderToStaticMarkup(
    createElement(
      MemoryRouter,
      null,
      createElement(NicheKeywordsView, {
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
const renderDetail = (props: Partial<Parameters<typeof KeywordClusterView>[0]>) =>
  renderToStaticMarkup(
    createElement(
      MemoryRouter,
      null,
      createElement(KeywordClusterView, {
        nicheId: 'n1',
        state: 'ready',
        cluster: detail,
        decisionError: null,
        onDecision: noop,
        onWatch: noop,
        onAcknowledge: noop,
        onRetry: noop,
        ...props,
      }),
    ),
  )

describe('TC_E3_FR028_03 danh sách cluster', () => {
  beforeAll(async () => {
    await i18n.changeLanguage('vi')
  })

  it('2 tab, chú thích, rỗng/lỗi', () => {
    const html = renderList({})
    expect(html).toContain('Cluster xếp hạng')
    expect(html).toContain('Cần nghiên cứu thêm')
    expect(html).toContain('không phải dự báo traffic hay doanh thu')
    expect(html).toContain('Chưa có cluster keyword nào')
    expect(renderList({ state: 'error', errorCode: 'KEYWORD_RUN_ACTIVE' })).toContain('đang có lượt nghiên cứu keyword')
  })

  it('điểm, intent, số keyword, MOCK, liên kết chi tiết', () => {
    const html = renderList({ items: [item] })
    expect(html).toContain('71.25')
    expect(html).toContain('3 keyword · 2 long-tail')
    expect(html).toContain('Thông tin')
    expect(html).toContain('data-testid="mock-badge"')
    expect(html).toContain('href="/niches/n1/keywords/c1"')
  })
})

describe('TC_E3_FR009_04 chi tiết cluster', () => {
  it('chỉ số không nguồn hiển thị UNKNOWN; intent có tín hiệu; cờ thương hiệu', () => {
    const html = renderDetail({})
    expect(html.match(/data-testid="metric-unknown"/g)?.length).toBe(3)
    expect(html).toContain('Có tín hiệu SERP')
    expect(html).toContain('Từ khóa thương hiệu')
    expect(html).toContain('Còn thiếu: Khoảng trống nội dung')
  })

  it('SERP, cảnh báo, gap, kênh, persona, strategy, quyết định', () => {
    const html = renderDetail({})
    expect(html).toContain('SERP đã thay đổi (phiên bản 2)')
    expect(html).toContain('bakersforum.example')
    expect(html).toContain('[MOCK] Too pricey')
    expect(html).toContain('data-status="UNKNOWN"')
    expect(html).toContain('[MOCK] never run out')
    expect(html).toContain('Hướng dẫn')
    expect(html).toContain('Ghi quyết định')
    const noSerp = renderDetail({ cluster: { ...detail, serp: [], content_gaps: { status: 'UNKNOWN', items: [] } } })
    expect(noSerp).toContain('data-testid="serp-unknown"')
    expect(noSerp).toContain('chưa phân tích trang đối thủ')
    expect(renderDetail({ state: 'loading' })).toContain('Đang tải…')
  })
})

describe('TC_E3_SC006_01 song ngữ', () => {
  it('khóa keywords có ở cả VI và EN', () => {
    const keys = (o: object, p = ''): string[] =>
      Object.entries(o).flatMap(([k, v]) => (typeof v === 'object' ? keys(v as object, `${p}${k}.`) : [`${p}${k}`]))
    expect(keys((en as Record<string, object>).keywords).sort()).toEqual(keys((vi as Record<string, object>).keywords).sort())
  })

  it('chuyển tiếng Anh', async () => {
    await i18n.changeLanguage('en')
    expect(renderList({ items: [item] })).toContain('not a traffic or revenue forecast')
    expect(renderDetail({})).toContain('SERP changed (version 2)')
    await i18n.changeLanguage('vi')
  })
})
