// E4 chi tiết job (FR-013): tham số không bí mật, kết quả/mã lỗi thân thiện (không stack trace), các bước, thao tác hợp lệ.
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import type { Job, JobAction, JobStep } from '@/api/dashboard'
import { MockBadge } from '@/components/MockBadge'
import { Alert, Card } from '@/components/ui/form'
import { formatDateTime, formatMoney } from '@/i18n'
import { LoadError, Loading, type LoadState } from '@/pages/dashboard/common'
import { JobActions } from '@/pages/dashboard/JobsView'

export interface JobDetailViewProps {
  state: LoadState
  errorCode?: string
  job?: Job
  steps: JobStep[]
  actionError: string | null
  onAction: (jobId: string, action: JobAction) => void
  onRetry: () => void
  confirm?: (message: string) => boolean
}

export function JobDetailView(props: JobDetailViewProps) {
  const { t } = useTranslation()
  if (props.state === 'loading') return <Loading />
  if (props.state === 'error' || !props.job) return <LoadError code={props.errorCode} onRetry={props.onRetry} />
  const j = props.job
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold">{j.job_type}</h1>
        {j.data_origin === 'MOCK' && <MockBadge />}
        <Link to="/jobs" className="ml-auto text-sm underline">
          {t('dashboard.jobs.back')}
        </Link>
      </div>
      <Card className="space-y-2 text-sm">
        <p data-testid="job-detail-status">
          {t('dashboard.jobs.col.status')}: {t(`dashboard.jobs.status.${j.status}`, j.status)}
        </p>
        {j.status_reason_code && (
          <Alert data-testid="job-reason">{t(`errors.${j.status_reason_code}`, t('dashboard.jobs.reasonCode', { code: j.status_reason_code }))}</Alert>
        )}
        <p>
          {t('dashboard.jobs.col.created')}: {formatDateTime(j.created_at)} · {t('dashboard.jobs.col.cost')}:{' '}
          {j.cost_accumulated_usd ? formatMoney(j.cost_accumulated_usd) : t('dashboard.unknown')} · {t('dashboard.jobs.aiCalls')}: {j.ai_call_count}
        </p>
        <JobActions job={j} onAction={props.onAction} confirm={props.confirm} />
        {props.actionError && <Alert>{t(`errors.${props.actionError}`, t('errors.generic'))}</Alert>}
        <details>
          <summary className="cursor-pointer">{t('dashboard.jobs.params')}</summary>
          <pre className="overflow-x-auto text-xs">{JSON.stringify(j.params, null, 2)}</pre>
        </details>
      </Card>
      <Card className="space-y-2">
        <h2 className="text-lg font-semibold">{t('dashboard.jobs.steps')}</h2>
        {props.steps.length === 0 ? (
          <p className="text-sm text-slate-500">{t('dashboard.jobs.noSteps')}</p>
        ) : (
          <ol className="space-y-1 text-sm">
            {props.steps.map((s) => (
              <li key={s.seq} data-testid="job-step">
                #{s.seq} {s.name} · {t(`dashboard.jobs.stepStatus.${s.status}`, s.status)}
                {s.error_code && <span className="text-red-700"> · {t(`errors.${s.error_code}`, s.error_code)}</span>}
              </li>
            ))}
          </ol>
        )}
      </Card>
    </div>
  )
}
