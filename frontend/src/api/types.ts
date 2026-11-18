// Kiểu dữ liệu theo contracts/openapi.yaml (phần dùng trong E0).
import type { Locale } from '../i18n'

export interface Me {
  id: string
  username: string
  ui_locale: Locale
  last_login_at: string | null
}

export interface ProviderStatus {
  provider: 'anthropic' | 'openai' | 'mock'
  configured: boolean
  key_hint: string | null
  last_check: string | null
}

export type ComponentState = 'OK' | 'UNAVAILABLE' | 'STALE' | 'NOT_RUNNING'

export interface SystemStatus {
  version: string
  app_env: 'development' | 'test' | 'production'
  database: ComponentState
  worker: ComponentState
  schema_revision: string | null
  paid_calls_enabled: boolean
  provider_override: string | null
  providers: ProviderStatus[]
  log_storage?: { retention_days: number; warning: boolean } | null
}
