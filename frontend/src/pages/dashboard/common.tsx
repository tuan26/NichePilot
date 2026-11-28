// E4 – thành phần dùng chung: trạng thái tải/lỗi/rỗng có hướng dẫn (FR-008, QA-13), ô điểm kèm Confidence (FR-012).
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Button } from '@/components/ui/button'
import { Alert } from '@/components/ui/form'

export type LoadState = 'loading' | 'error' | 'ready'


export function Loading() {
  const { t } = useTranslation()
  return <p className="text-sm text-slate-500">{t('app.loading')}</p>
}

export function LoadError({ code, onRetry }: { code?: string; onRetry: () => void }) {
  const { t } = useTranslation()
  return (
    <Alert className="flex items-center justify-between gap-4" data-testid="load-error">
      <span>{t(`errors.${code ?? 'generic'}`, t('errors.generic'))}</span>
      <Button size="sm" variant="outline" onClick={onRetry}>
        {t('app.retry')}
      </Button>
    </Alert>
  )
}

export function Empty({ children }: { children: ReactNode }) {
  return (
    <p className="text-sm text-slate-500" data-testid="empty-state">
      {children}
    </p>
  )
}

export function Score({ opportunity, confidence }: { opportunity: number | null; confidence: number | null }) {
  const { t } = useTranslation()
  return (
    <span data-testid="score">
      {t('dashboard.score.opportunity')}: {opportunity ?? t('dashboard.unknown')} · {t('dashboard.score.confidence')}:{' '}
      {confidence ?? t('dashboard.unknown')}
    </span>
  )
}

export function MockToggle({ checked, onChange }: { checked: boolean; onChange: (v: boolean) => void }) {
  const { t } = useTranslation()
  return (
    <label className="flex items-center gap-2 text-sm">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} data-testid="dashboard-include-mock" />
      {t('dashboard.includeMock')}
    </label>
  )
}
