// Nhãn "Dữ liệu giả lập" – dữ liệu MOCK không bao giờ được trình bày như kết quả thật (Constitution I).
import { useTranslation } from 'react-i18next'

export function MockBadge() {
  const { t } = useTranslation()
  return (
    <span
      data-testid="mock-badge"
      title={t('mock.hint')}
      className="inline-flex items-center rounded-full border border-amber-300 bg-amber-100 px-2.5 py-0.5 text-xs font-semibold text-amber-900"
    >
      {t('mock.badge')}
    </span>
  )
}
