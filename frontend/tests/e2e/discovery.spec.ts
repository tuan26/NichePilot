// T124 – E2E E1 (SC-014, SC-001): tạo lượt (≤ 3 thao tác) → bảng xếp hạng → nguồn → VI/EN, trên stack thật với nguồn GIẢ LẬP
// (DISCOVERY_SOURCE_MODE=mock, chỉ development) và MockAIProvider – không mạng ngoài, không API có phí.
// Nguồn ALLOWED dùng ở đây là nguồn TEST tạo trong DB E2E (adapter giả lập); nguồn seed thật vẫn UNVERIFIED và không được bật.
// MockAIProvider trả danh sách ứng viên rỗng → lượt hoàn tất với 0 ngách (trung thực, không bịa dữ liệu); luồng chi tiết ngách và
// ghi quyết định được kiểm thử bằng contract test backend + vitest (NOT_TESTED ở E2E – ghi trong checklists/verification.md).
// Yêu cầu: database trống. Chạy riêng: E2E_SUITE=discovery npm run test:e2e
import { expect, type Page, test } from '@playwright/test'

const USER = 'owner'
// Mật khẩu dùng một lần cho DB E2E: CI sinh ngẫu nhiên mỗi lần chạy (E2E_OWNER_PASSWORD) – không có giá trị cố định trong repo
const PASSWORD = process.env.E2E_OWNER_PASSWORD ?? ''

async function api(page: Page, method: 'POST' | 'PUT', path: string, data: unknown) {
  const cookies = await page.context().cookies()
  const csrf = cookies.find((c) => c.name === 'np_csrf')?.value ?? ''
  const r = await page.request.fetch(path, { method, data, headers: { 'X-CSRF-Token': csrf } })
  expect(r.ok(), `${method} ${path}: ${r.status()} ${await r.text()}`).toBeTruthy()
  return r.json()
}

test('E1: tạo lượt → xếp hạng → nguồn → VI/EN', async ({ page }) => {
  expect(PASSWORD.length, 'đặt E2E_OWNER_PASSWORD (≥ 12 ký tự) trước khi chạy E2E_SUITE=discovery').toBeGreaterThanOrEqual(12)
  await page.goto('/')
  await expect(page).toHaveURL(/\/setup$/)
  await page.getByLabel('Tên đăng nhập').fill(USER)
  await page.getByLabel('Mật khẩu', { exact: true }).fill(PASSWORD)
  await page.getByLabel('Nhập lại mật khẩu').fill(PASSWORD)
  await page.getByRole('button', { name: 'Tạo tài khoản' }).click()
  await expect(page.getByRole('heading', { name: 'Trạng thái hệ thống' })).toBeVisible()

  // Nguồn TEST (giả lập) – chủ sở hữu xác minh ALLOWED trong DB E2E; chỉ nguồn ALLOWED mới bật được
  const src = await api(page, 'POST', '/api/v1/sources', {
    source_key: 'e2e:mock-engine',
    display_name: 'E2E mock engine',
    adapter_type: 'searxng_engine',
    tos_url: 'https://tos.example/e2e',
    config: { engine_name: 'e2emock' },
  })
  await api(page, 'PUT', `/api/v1/sources/${src.id}`, {
    compliance_status: 'ALLOWED',
    verified_at: '2026-11-01',
    verification_note: 'Nguồn giả lập chỉ dùng trong E2E',
    allowed_access_methods: ['SEARXNG_ENGINE'],
    permitted_use_scope: 'Chỉ dùng trong E2E tự động',
    enabled: true,
  })

  // Tạo lượt: 2 thao tác (mở trang, bấm chạy) – thị trường mặc định US, không chọn lĩnh vực
  await page.goto('/discovery/runs')
  await page.getByRole('button', { name: 'Chạy lượt khám phá' }).click()
  const row = page.getByTestId('run-row').first()
  await expect(row).toBeVisible()
  await expect(row.getByTestId('mock-badge')).toBeVisible()
  await expect(row.getByTestId('run-outcome')).toContainText('Hoàn tất', { timeout: 60_000 })
  await expect(row.getByTestId('report-download')).toBeVisible()

  // Bảng xếp hạng: 3 tab, chú thích "không phải dự báo doanh thu"
  await page.getByRole('link', { name: 'Bảng xếp hạng' }).click()
  await expect(page.getByRole('heading', { name: 'Bảng xếp hạng ngách' })).toBeVisible()
  await expect(page.getByText('không phải dự báo doanh thu')).toBeVisible()
  for (const tab of ['Cơ hội nghiên cứu', 'Ưu tiên affiliate', 'Cần nghiên cứu thêm']) {
    await page.getByRole('tab', { name: tab }).click()
    await expect(page.getByText('Chưa có ngách nào trong danh sách này.')).toBeVisible()
  }

  // Nguồn: seed UNVERIFIED không có nút bật; nguồn test ALLOWED có nút tắt
  await page.goto('/sources')
  const seed = page.getByTestId('source-row').filter({ hasText: 'searxng:wikipedia' })
  await expect(seed).toContainText('UNVERIFIED')
  await expect(seed.getByRole('button', { name: 'Bật nguồn' })).toHaveCount(0)
  await expect(page.getByTestId('source-row').filter({ hasText: 'e2e:mock-engine' })).toContainText('ALLOWED')

  // EN
  await page.getByRole('button', { name: 'EN' }).click()
  await expect(page.getByRole('heading', { name: 'Data sources' })).toBeVisible()
  await page.goto('/niches')
  await expect(page.getByRole('heading', { name: 'Niche ranking' })).toBeVisible()
  await expect(page.getByText('not a revenue forecast')).toBeVisible()
})

// Ngách DEMO gắn MOCK do `python -m nichepilot.jobs.discovery_demo_seed` nạp trước khi chạy (chỉ dev/test – chủ sở hữu duyệt
// 2026-11-25). Không phải dữ liệu nghiên cứu; ẩn khỏi xếp hạng mặc định; không liên quan SC-013.
test('E2 MOCK: ngách → sản phẩm (hiện MOCK) → chi tiết → quyết định → EN', async ({ page }) => {
  expect(PASSWORD.length).toBeGreaterThanOrEqual(12)
  await page.goto('/login')
  await page.getByLabel('Tên đăng nhập').fill(USER)
  await page.getByLabel('Mật khẩu', { exact: true }).fill(PASSWORD)
  await page.getByRole('button', { name: 'Đăng nhập' }).click()
  await expect(page.getByRole('heading', { name: 'Trạng thái hệ thống' })).toBeVisible()

  await page.goto('/niches')
  await page.getByLabel('Hiện dữ liệu giả lập (MOCK)').check()
  await page.getByTestId('ranking-row').filter({ hasText: '[MOCK DEMO]' }).getByRole('link').click()
  // Tóm tắt E2 trên trang ngách E1 (chỉ hiển thị, không đổi dữ liệu E1)
  await expect(page.getByTestId('product-summary')).toContainText('2 sản phẩm')
  await page.getByTestId('open-products').click()

  await expect(page.getByRole('heading', { name: 'Sản phẩm & affiliate' })).toBeVisible()
  await expect(page.getByText('Chưa có sản phẩm nào')).toBeVisible() // MOCK ẩn mặc định
  await page.getByLabel('Hiện dữ liệu giả lập (MOCK)').check()
  const row = page.getByTestId('product-row').filter({ hasText: '[MOCK DEMO] ShelfAlert' })
  await expect(row).toBeVisible()
  await expect(row.getByTestId('readiness')).toHaveText('Đủ điều kiện tham gia')
  await expect(row.getByTestId('mock-badge')).toBeVisible()
  await expect(page.getByText('không phải dự báo doanh thu')).toBeVisible()
  await row.getByRole('link').click()

  await expect(page.getByRole('heading', { name: '[MOCK DEMO] ShelfAlert' })).toBeVisible()
  await expect(page.getByTestId('program-status')).toHaveText('Đã xác minh')
  await expect(page.getByTestId('attr-price')).toContainText('https://shelfalert-demo.example/pricing')
  await page.getByTestId('product-decision-select').selectOption('WATCH')
  await page.getByLabel('Lý do (bắt buộc)').fill('E2E: theo dõi thêm (dữ liệu MOCK)')
  await page.getByRole('button', { name: 'Ghi quyết định' }).click()
  await expect(page.getByTestId('product-decision')).toContainText('Theo dõi')

  await page.getByRole('button', { name: 'EN' }).click()
  await expect(page.getByTestId('readiness')).toHaveText('Eligible to join')
  await page.getByRole('button', { name: 'VI' }).click()
})

test('E3 MOCK: ngách → keyword (hiện MOCK) → cluster → chỉ số UNKNOWN → quyết định → EN', async ({ page }) => {
  expect(PASSWORD.length).toBeGreaterThanOrEqual(12)
  await page.goto('/login')
  await page.getByLabel('Tên đăng nhập').fill(USER)
  await page.getByLabel('Mật khẩu', { exact: true }).fill(PASSWORD)
  await page.getByRole('button', { name: 'Đăng nhập' }).click()
  await expect(page.getByRole('heading', { name: 'Trạng thái hệ thống' })).toBeVisible()

  await page.goto('/niches')
  await page.getByLabel('Hiện dữ liệu giả lập (MOCK)').check()
  await page.getByTestId('ranking-row').filter({ hasText: '[MOCK DEMO]' }).getByRole('link').click()
  // Tóm tắt E3 trên trang ngách E1 (chỉ hiển thị, không đổi dữ liệu E1)
  await expect(page.getByTestId('keyword-summary')).toContainText('long-tail')
  await page.getByTestId('open-keywords').click()

  await expect(page.getByRole('heading', { name: 'Keyword & audience' })).toBeVisible()
  await expect(page.getByText('Chưa có cluster keyword nào')).toBeVisible() // MOCK ẩn mặc định
  await page.getByTestId('keywords-include-mock').check()
  await expect(page.getByText('không phải dự báo traffic hay doanh thu')).toBeVisible()
  const row = page.getByTestId('cluster-row').filter({ hasText: 'how to stop running out of ingredients' })
  await expect(row).toBeVisible()
  await expect(row.getByTestId('mock-badge')).toBeVisible()
  await row.getByRole('link').click()

  await expect(page.getByRole('heading', { name: 'how to stop running out of ingredients in a micro bakery' })).toBeVisible()
  await expect(page.getByTestId('metric-unknown').first()).toHaveText('UNKNOWN') // không có nguồn chỉ số keyword
  await expect(page.getByText('bakersforum-demo.example').first()).toBeVisible()
  await page.getByTestId('cluster-decision-select').selectOption('WATCH')
  await page.getByLabel('Lý do (bắt buộc)').fill('E2E: theo dõi thêm (dữ liệu MOCK)')
  await page.getByRole('button', { name: 'Ghi quyết định' }).click()
  await expect(page.getByTestId('cluster-decision')).toContainText('Theo dõi')

  await page.getByRole('button', { name: 'EN' }).click()
  await expect(page.getByText('not a traffic or revenue forecast')).toBeVisible()
  await page.getByRole('button', { name: 'VI' }).click()
})

// TC_E4_FR022_01 TC_E4_SC005_01 – luồng end-to-end dashboard E4 (MOCK)
test('E4 MOCK: tổng quan → sản phẩm → keyword → jobs → chi phí → cài đặt → EN', async ({ page }) => {
  expect(PASSWORD.length).toBeGreaterThanOrEqual(12)
  await page.goto('/login')
  await page.getByLabel('Tên đăng nhập').fill(USER)
  await page.getByLabel('Mật khẩu', { exact: true }).fill(PASSWORD)
  await page.getByRole('button', { name: 'Đăng nhập' }).click()
  await expect(page.getByRole('heading', { name: 'Trạng thái hệ thống' })).toBeVisible()

  await page.getByTestId('nav-overview').click()
  await expect(page.getByRole('heading', { name: 'Tổng quan' })).toBeVisible()
  await expect(page.getByTestId('nav-overview')).toHaveAttribute('aria-current', 'page')
  await page.getByTestId('dashboard-include-mock').check()
  await expect(page.getByTestId('top-niche').filter({ hasText: '[MOCK DEMO]' })).toBeVisible()
  await expect(page.getByTestId('overview-costs')).toContainText('không tính vào chi phí thực')

  await page.getByTestId('nav-products').click()
  await expect(page.getByRole('heading', { name: 'Product Discovery' })).toBeVisible()
  await page.getByTestId('dashboard-include-mock').check()
  await expect(page.getByTestId('research-row').filter({ hasText: '[MOCK DEMO]' })).toContainText('sẵn sàng affiliate')

  await page.getByTestId('nav-keywords').click()
  await page.getByTestId('dashboard-include-mock').check()
  const kwRow = page.getByTestId('research-row').filter({ hasText: '[MOCK DEMO]' })
  await expect(kwRow).toContainText('long-tail')
  await kwRow.getByRole('link').first().click()
  await expect(page.getByRole('heading', { name: 'Keyword & audience' })).toBeVisible()

  await page.getByTestId('nav-jobs').click()
  await expect(page.getByRole('heading', { name: 'Agent jobs' })).toBeVisible()
  await expect(page.getByTestId('job-row').first()).toBeVisible()

  await page.getByTestId('nav-costs').click()
  await expect(page.getByTestId('costs-mock')).toBeVisible()

  await page.getByTestId('nav-settings').click()
  await expect(page.getByTestId('ai-readonly')).toBeVisible()
  await expect(page.getByTestId('paid-calls-state')).toContainText('TẮT')

  await page.getByRole('button', { name: 'EN' }).click()
  await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible()
  await page.reload()
  await expect(page.getByRole('heading', { name: 'Settings' })).toBeVisible() // ghi nhớ ngôn ngữ
  await page.getByRole('button', { name: 'VI' }).click()
})

test('E1 MOCK: xếp hạng (hiện MOCK) → chi tiết → ghi quyết định → xóa bằng chứng', async ({ page }) => {
  expect(PASSWORD.length).toBeGreaterThanOrEqual(12)
  await page.goto('/login')
  await page.getByLabel('Tên đăng nhập').fill(USER)
  await page.getByLabel('Mật khẩu', { exact: true }).fill(PASSWORD)
  await page.getByRole('button', { name: 'Đăng nhập' }).click()
  await expect(page.getByRole('heading', { name: 'Trạng thái hệ thống' })).toBeVisible()

  await page.goto('/niches')
  await expect(page.getByText('Chưa có ngách nào trong danh sách này.')).toBeVisible() // MOCK ẩn mặc định
  await page.getByLabel('Hiện dữ liệu giả lập (MOCK)').check()
  const row = page.getByTestId('ranking-row').filter({ hasText: '[MOCK DEMO]' })
  await expect(row).toBeVisible()
  await expect(row.getByTestId('opportunity')).toHaveText('60.71')
  await expect(row.getByTestId('mock-badge')).toBeVisible()
  await row.getByRole('link').click()

  // Chi tiết: nhãn MOCK, lý do chấm điểm, pain point, bằng chứng + nguồn
  await expect(page.getByRole('heading', { name: /\[MOCK DEMO\]/ })).toBeVisible()
  await expect(page.getByTestId('scoring')).toContainText('60.71')
  await expect(page.getByTestId('evidence-status')).toHaveText('Đủ bằng chứng')
  await expect(page.getByTestId('evidence-item')).toHaveCount(2)
  await expect(page.getByText('[MOCK DEMO] Ingredients run out without warning')).toBeVisible()

  // Ghi quyết định (bắt buộc lý do) – đề xuất AI giữ nguyên
  const decision = page.getByTestId('decision')
  await decision.getByLabel('Quyết định').selectOption('WATCH')
  await decision.getByLabel('Lý do (bắt buộc)').fill('E2E: theo dõi thêm (dữ liệu MOCK)')
  await decision.getByRole('button', { name: 'Ghi quyết định' }).click()
  await expect(decision).toContainText('Theo dõi')
  await expect(page.getByTestId('scoring')).toContainText('Tiếp tục') // đề xuất AI (MOCK) không bị ghi đè

  // Xóa một bằng chứng (có xác nhận) → còn 1 nguồn → ngách tính lại thành chưa đủ bằng chứng
  await page.getByTestId('evidence-item').first().getByRole('button', { name: 'Xóa bằng chứng' }).click()
  const confirm = page.getByTestId('erase-confirm')
  await expect(confirm).toContainText('không thể hoàn tác')
  await confirm.getByLabel('Lý do (bắt buộc)').fill('E2E erase test (MOCK)')
  await confirm.getByRole('button', { name: 'Xác nhận xóa' }).click()
  await expect(page.getByTestId('evidence-item')).toHaveCount(1)
  await expect(page.getByTestId('evidence-status')).toHaveText('Chưa đủ bằng chứng')

  await page.getByRole('button', { name: 'EN' }).click()
  await expect(page.getByTestId('evidence-status')).toHaveText('Insufficient evidence')
})
