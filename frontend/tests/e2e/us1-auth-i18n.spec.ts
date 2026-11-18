// T047 – US1 E2E: khởi tạo tài khoản, trạng thái, chuyển VI/EN, đăng xuất, khóa tạm (US1 kịch bản 1–6).
// Yêu cầu: database trống (chưa có tài khoản). Chạy trên stack với MockAIProvider, không gọi API có phí.
import { expect, test } from '@playwright/test'

const USER = 'owner'
const PASSWORD = 'e2e-only-password-123' // chỉ dùng cho E2E

test('US1: khởi tạo → trạng thái → VI/EN → đăng xuất → khóa tạm', async ({ page }) => {
  // Kịch bản 2: lần đầu → bắt buộc khởi tạo tài khoản, giao diện mặc định tiếng Việt
  await page.goto('/')
  await expect(page).toHaveURL(/\/setup$/)
  await expect(page.getByRole('heading', { name: 'Khởi tạo tài khoản quản trị' })).toBeVisible()
  await expect(page.locator('html')).toHaveAttribute('lang', 'vi')

  // Mật khẩu nhập lại không khớp → báo lỗi bằng tiếng Việt
  await page.getByLabel('Tên đăng nhập').fill(USER)
  await page.getByLabel('Mật khẩu', { exact: true }).fill(PASSWORD)
  await page.getByLabel('Nhập lại mật khẩu').fill('khac-mat-khau-123')
  await page.getByRole('button', { name: 'Tạo tài khoản' }).click()
  await expect(page.getByRole('alert')).toHaveText('Mật khẩu nhập lại không khớp.')

  await page.getByLabel('Nhập lại mật khẩu').fill(PASSWORD)
  await page.getByRole('button', { name: 'Tạo tài khoản' }).click()

  // Kịch bản 1, 5: trang trạng thái; provider chưa cấu hình không phải lỗi; chế độ giả lập + gọi có phí TẮT
  await expect(page.getByRole('heading', { name: 'Trạng thái hệ thống' })).toBeVisible()
  await expect(page.getByText('Cơ sở dữ liệu')).toBeVisible()
  await expect(page.getByTestId('mock-badge')).toHaveText('Dữ liệu giả lập')
  await expect(page.getByTestId('paid-calls')).toHaveText('TẮT')
  await expect(page.getByText('Chưa cấu hình').first()).toBeVisible()

  // Kịch bản 6: chuyển EN có hiệu lực ngay (không tải lại trang)
  const navigations: string[] = []
  page.on('framenavigated', (f) => navigations.push(f.url()))
  await page.getByRole('button', { name: 'EN' }).click()
  await expect(page.getByRole('heading', { name: 'System status' })).toBeVisible()
  await expect(page.getByTestId('mock-badge')).toHaveText('Simulated data')
  await expect(page.locator('html')).toHaveAttribute('lang', 'en')
  expect(navigations).toEqual([])

  // Ghi nhớ lựa chọn sau khi tải lại
  await page.reload()
  await expect(page.getByRole('heading', { name: 'System status' })).toBeVisible()

  // Đăng xuất → về trang đăng nhập (tiếng Anh vẫn được giữ)
  await page.getByRole('button', { name: 'Sign out' }).click()
  await expect(page).toHaveURL(/\/login$/)
  await expect(page.getByRole('heading', { name: 'Sign in' })).toBeVisible()

  // Quay lại tiếng Việt cho phần kiểm tra khóa tạm
  await page.getByRole('button', { name: 'VI' }).click()

  // Kịch bản 4: sai mật khẩu 5 lần → lần 6 bị khóa, có thời điểm mở khóa; thông báo không lộ chi tiết kỹ thuật
  await page.getByLabel('Tên đăng nhập').fill(USER)
  for (let i = 0; i < 5; i++) {
    await page.getByLabel('Mật khẩu').fill(`sai-mat-khau-${i}-xx`)
    await page.getByRole('button', { name: 'Đăng nhập' }).click()
    await expect(page.getByRole('alert')).toHaveText('Tên đăng nhập hoặc mật khẩu không đúng.')
  }
  await page.getByLabel('Mật khẩu').fill(PASSWORD)
  await page.getByRole('button', { name: 'Đăng nhập' }).click()
  await expect(page.getByRole('alert')).toContainText('Tài khoản bị khóa tạm thời đến')
  await expect(page.getByRole('alert')).not.toContainText(/Traceback|Exception|SELECT/i)
})
