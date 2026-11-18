import { defineConfig, devices } from '@playwright/test'

// E2E chạy trên stack thật (MockAIProvider, gọi API có phí TẮT). Base URL mặc định: Compose (http://localhost:8080).
export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [['list']],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:8080',
    trace: 'off',
    locale: 'vi-VN',
    // Môi trường có Chromium dựng sẵn khác phiên bản: đặt PW_CHROMIUM_PATH để dùng bản đó (CI không cần).
    launchOptions: process.env.PW_CHROMIUM_PATH ? { executablePath: process.env.PW_CHROMIUM_PATH } : {},
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
})
