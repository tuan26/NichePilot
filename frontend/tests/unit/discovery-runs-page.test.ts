// T060 – Màn hình 1 "Lượt khám phá" (FR-026): đang tải / rỗng / lỗi / có dữ liệu, nhãn MOCK, chi phí REAL/MOCK,
// thông báo NO_COMPLIANT_SEARCH_SOURCE, không có tùy chọn dùng nguồn chưa xác minh (quyết định A1).
// Render tĩnh bằng react-dom/server – không thêm thư viện test mới. Test case: TC_E1_FR026_01.
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { beforeAll, describe, expect, it } from 'vitest'
import type { DiscoveryRun } from '../../src/api/types'
import i18n from '../../src/i18n'
import { DiscoveryRunsView } from '../../src/pages/discovery/DiscoveryRunsView'

const run: DiscoveryRun = {
  id: 'r1',
  job: { job_id: 'j1', job_type: 'discovery.run', status: 'SUCCEEDED' },
  market: 'US',
  research_language: 'en',
  seed_topic: null,
  max_candidates: 20,
  budget_usd: '2.000000',
  time_limit_minutes: 90,
  page_limit: 300,
  per_domain_interval_s: 2,
  weights_version: 1,
  source_mode: 'MOCK',
  trigger: 'MANUAL',
  sources: [{ source_key: 'test:mock-engine', verified_at: '2026-11-01' }],
  outcome: 'PARTIAL_COMPLETED',
  stop_reason: 'PAGE_LIMIT_REACHED',
  metrics: { pages_succeeded: 3, pages_skipped: 1, pages_failed: 0, candidates: 3, cost_real_usd: '0', cost_mock_usd: '0.0007' },
  data_origin: 'MOCK',
  created_at: '2026-11-20T06:00:00Z',
}

const noop = () => undefined
const render = (props: Partial<Parameters<typeof DiscoveryRunsView>[0]>) =>
  renderToStaticMarkup(
    createElement(DiscoveryRunsView, {
      state: 'ready',
      runs: [],
      onCreate: noop,
      onAction: noop,
      onRetry: noop,
      creating: false,
      createError: null,
      ...props,
    }),
  )

describe('TC_E1_FR026_01 màn hình lượt khám phá', () => {
  beforeAll(async () => {
    await i18n.changeLanguage('vi')
  })

  it('hiển thị trạng thái đang tải, rỗng, lỗi', () => {
    expect(render({ state: 'loading' })).toContain('Đang tải…')
    expect(render({ state: 'ready', runs: [] })).toContain('Chưa có lượt khám phá nào')
    expect(render({ state: 'error', errorCode: 'ERASURE_LEDGER_NOT_APPLIED' })).toContain('Sổ xóa bằng chứng chưa được áp dụng')
  })

  it('hiển thị lượt: kết quả + lý do dừng, chi phí tách thật/giả lập, nhãn MOCK, thao tác', () => {
    const html = render({ runs: [run] })
    expect(html).toContain('Hoàn tất một phần')
    expect(html).toContain('Đạt giới hạn số trang')
    expect(html).toContain('data-testid="mock-badge"')
    expect(html).toContain('0.0007')
    expect(html).toContain('data-testid="run-cost-real"')
    expect(html).toContain('test:mock-engine')
    expect(html).toContain('data-testid="report-download"')
    expect(html).toContain('format=markdown')
  })

  it('báo lỗi không có nguồn hợp lệ và không có tùy chọn nguồn chưa xác minh', () => {
    const html = render({ createError: 'NO_COMPLIANT_SEARCH_SOURCE' })
    expect(html).toContain('Chưa có nguồn dữ liệu nào được xác minh ALLOWED')
    expect(html.toLowerCase()).not.toContain('unverified')
    expect(html).not.toContain('include_unverified')
  })

  it('chuyển tiếng Anh', async () => {
    await i18n.changeLanguage('en')
    expect(render({ state: 'ready', runs: [] })).toContain('No discovery runs yet')
    await i18n.changeLanguage('vi')
  })
})
