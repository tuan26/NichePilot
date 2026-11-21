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
