// E4 – khóa cấu hình không bí mật được sửa từ trang Cài đặt (FR-017; FR-055 E0).
export const EDITABLE_SETTINGS = [
  'system.timezone',
  'ui.default_locale',
  'agent.default_max_steps',
  'agent.default_max_ai_calls',
  'agent.default_job_timeout_s',
] as const
