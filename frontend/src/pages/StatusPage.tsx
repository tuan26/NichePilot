// Trang trạng thái hệ thống (T056 – FR-002, FR-057, UI-05): loading / error / empty states.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useTranslation } from 'react-i18next'
import { Link, useNavigate } from 'react-router'
import { api, errorKey } from '@/api/client'
import type { ComponentState, SystemStatus } from '@/api/types'
import { Layout } from '@/app/Layout'
import { MockBadge } from '@/components/MockBadge'
import { Button } from '@/components/ui/button'
import { Alert, Card } from '@/components/ui/form'
import { formatDateTime } from '@/i18n'

function StateBadge({ state }: { state: ComponentState }) {
  const { t } = useTranslation()
  const tone = state === 'OK' ? 'bg-emerald-100 text-emerald-800' : 'bg-red-100 text-red-800'
  return <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${tone}`}>{t(`status.state.${state}`)}</span>
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-slate-100 py-3 last:border-0">
      <dt className="text-sm text-slate-600">{label}</dt>
      <dd className="text-sm font-medium">{children}</dd>
    </div>
  )
}

export function StatusPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const status = useQuery({
    queryKey: ['system-status'],
    queryFn: () => api<SystemStatus>('/api/v1/system/status'),
    refetchInterval: 30_000,
  })
  const logout = useMutation({
    mutationFn: () => api('/api/v1/auth/logout', { method: 'POST' }),
    onSettled: async () => {
      await qc.invalidateQueries()
      void navigate('/login', { replace: true })
    },
  })

  const s = status.data
  const isMock = s?.provider_override === 'mock'

  return (
    <Layout
      syncProfile
      actions={
        <>
          <Link to="/discovery/runs" className="text-sm text-slate-600 underline" data-testid="nav-discovery">
            {t('nav.discovery')}
          </Link>
          <Button variant="outline" size="sm" onClick={() => logout.mutate()}>
            {t('app.logout')}
          </Button>
        </>
      }
    >
      <div className="mb-6 flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold">{t('status.title')}</h1>
        {isMock && <MockBadge />}
      </div>
      <p className="mb-6 text-sm text-slate-600">{t('status.description')}</p>

      {status.isPending && <p className="text-sm text-slate-500">{t('app.loading')}</p>}
      {status.isError && (
        <Alert className="flex items-center justify-between gap-4">
          <span>{t(errorKey(status.error))}</span>
          <Button size="sm" variant="outline" onClick={() => void status.refetch()}>
            {t('app.retry')}
          </Button>
        </Alert>
      )}
      {status.isSuccess && !s && <p className="text-sm text-slate-500">{t('status.empty')}</p>}

      {s && (
        <div className="grid gap-6 md:grid-cols-2">
          {s.log_storage?.warning && (
            <Alert variant="warning" className="md:col-span-2">
              {t('status.logWarning')}
            </Alert>
          )}
          <Card>
            <dl>
              <Row label={t('status.database')}>
                <StateBadge state={s.database} />
              </Row>
              <Row label={t('status.worker')}>
                <StateBadge state={s.worker} />
              </Row>
              <Row label={t('status.aiMode')}>{isMock ? t('status.aiModeMock') : t('status.aiModeReal')}</Row>
              <Row label={t('status.paidCalls')}>
                <span data-testid="paid-calls">{s.paid_calls_enabled ? t('status.on') : t('status.off')}</span>
              </Row>
            </dl>
          </Card>
          <Card>
            <h2 className="mb-2 text-sm font-semibold">{t('status.providers')}</h2>
            <dl>
              {s.providers
                .filter((p) => p.provider !== 'mock')
                .map((p) => (
                  <Row key={p.provider} label={p.provider}>
                    {p.configured ? `${t('status.configured')} ${p.key_hint ?? ''}` : t('status.notConfigured')}
                  </Row>
                ))}
              <Row label={t('status.version')}>{s.version}</Row>
              <Row label={t('status.environment')}>{s.app_env}</Row>
              <Row label={t('status.schema')}>{s.schema_revision ?? '—'}</Row>
            </dl>
          </Card>
          <p className="text-xs text-slate-500 md:col-span-2">
            {t('status.updatedAt', { time: formatDateTime(new Date(status.dataUpdatedAt)) })}
          </p>
        </div>
      )}
    </Layout>
  )
}
