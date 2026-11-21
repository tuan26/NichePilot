// T110 – Màn hình quản lý nguồn (FR-006c, FR-006d, FR-026): danh sách + trạng thái tuân thủ; nút bật CHỈ cho nguồn ALLOWED; form xác
// minh đủ mục; thông báo cần khởi động lại SearXNG; không có tùy chọn bỏ qua cảnh báo (A1). Test case: TC_E1_FR006d_04.
import { createElement } from 'react'
import { renderToStaticMarkup } from 'react-dom/server'
import { beforeAll, describe, expect, it } from 'vitest'
import type { SourcePolicy } from '../../src/api/types'
import i18n from '../../src/i18n'
import { SourcesView } from '../../src/pages/discovery/SourcesView'

const base: SourcePolicy = {
  id: 's1',
  source_key: 'searxng:wikipedia',
  display_name: 'Wikipedia (MediaWiki)',
  adapter_type: 'searxng_engine',
  config: { engine_name: 'wikipedia' },
  tos_url: 'https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use',
  verified_at: null,
  verification_note: null,
  allowed_access_methods: [],
  permitted_use_scope: null,
  compliance_status: 'UNVERIFIED',
  known_limits: null,
  enabled: false,
  usable: false,
  verified_by: null,
  requires_service_restart: false,
}
const noop = () => undefined
const render = (props: Partial<Parameters<typeof SourcesView>[0]>) =>
  renderToStaticMarkup(
    createElement(SourcesView, { state: 'ready', sources: [], saving: false, error: null, restartNotice: false, onUpdate: noop, onRetry: noop, ...props }),
  )

describe('TC_E1_FR006d_04 màn hình nguồn', () => {
  beforeAll(async () => {
    await i18n.changeLanguage('vi')
  })

  it('nguồn UNVERIFIED không có nút bật; có form xác minh', () => {
    const html = render({ sources: [base] })
    expect(html).toContain('Wikipedia (MediaWiki)')
    expect(html).toContain('UNVERIFIED')
    expect(html).not.toContain('data-testid="enable-s1"')
    expect(html).toContain('data-testid="verify-s1"')
    expect(html.toLowerCase()).not.toContain('confirm_warning')
  })

  it('nguồn ALLOWED có nút bật; thông báo khởi động lại SearXNG', () => {
    const allowed = { ...base, compliance_status: 'ALLOWED' as const, verified_at: '2026-11-01' }
    const html = render({ sources: [allowed], restartNotice: true })
    expect(html).toContain('data-testid="enable-s1"')
    expect(html).toContain('khởi động lại dịch vụ searxng')
  })

  it('đang tải / lỗi / rỗng', () => {
    expect(render({ state: 'loading' })).toContain('Đang tải…')
    expect(render({ state: 'error', errorCode: 'SOURCE_NOT_ALLOWED' })).toContain('ALLOWED')
    expect(render({ sources: [] })).toContain('Chưa có nguồn nào')
  })
})
