// E4 Agent Jobs (FR-013…FR-015): danh sách job có lọc, thao tác theo trạng thái hợp lệ (máy trạng thái E0), lịch chạy bật/tắt/xóa.
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import type { Job, JobAction, Schedule } from '@/api/dashboard'
import { MockBadge } from '@/components/MockBadge'
import { Button } from '@/components/ui/button'
import { Alert, Card } from '@/components/ui/form'
import { formatDateTime, formatMoney } from '@/i18n'
import { allowedActions, JOB_STATUSES } from '@/lib/jobs'
import { Empty, LoadError, Loading, type LoadState } from '@/pages/dashboard/common'



export interface JobsViewProps {
  state: LoadState
  errorCode?: string
  jobs: Job[]
  total: number
  status: string
  jobType: string
  jobTypes: string[]
  schedules: Schedule[]
  actionError: string | null
  onStatusChange: (v: string) => void
  onJobTypeChange: (v: string) => void
  onAction: (jobId: string, action: JobAction) => void
  onToggleSchedule: (id: string, enabled: boolean) => void
  onDeleteSchedule: (id: string) => void
  onRetry: () => void
  confirm?: (message: string) => boolean
}

export function JobActions({ job, onAction, confirm }: { job: Job; onAction: (id: string, a: JobAction) => void; confirm?: (m: string) => boolean }) {
  const { t } = useTranslation()
  const ask = confirm ?? ((m: string) => window.confirm(m))
  return (
    <span className="flex flex-wrap gap-1">
      {allowedActions(job.status).map((a) => (
        <Button
          key={a}
          size="sm"
          variant={a === 'cancel' ? 'outline' : 'default'}
          data-testid={`job-${a}`}
          onClick={() => {
            if (a !== 'cancel' || ask(t('dashboard.jobs.confirmCancel'))) onAction(job.id, a)
          }}
        >
          {t(`dashboard.jobs.action.${a}`)}
        </Button>
      ))}
    </span>
  )
}

export function JobsView(props: JobsViewProps) {
  const { t } = useTranslation()
  const ask = props.confirm ?? ((m: string) => window.confirm(m))
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">{t('dashboard.jobs.title')}</h1>
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <label className="flex items-center gap-2">
          {t('dashboard.jobs.filterStatus')}
          <select
            className="rounded-md border border-slate-300 px-2 py-1"
            value={props.status}
            onChange={(e) => props.onStatusChange(e.target.value)}
            data-testid="filter-status"
          >
            <option value="">{t('dashboard.jobs.all')}</option>
            {JOB_STATUSES.map((s) => (
              <option key={s} value={s}>
                {t(`dashboard.jobs.status.${s}`)}
              </option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-2">
          {t('dashboard.jobs.filterType')}
          <select
            className="rounded-md border border-slate-300 px-2 py-1"
            value={props.jobType}
            onChange={(e) => props.onJobTypeChange(e.target.value)}
            data-testid="filter-type"
          >
            <option value="">{t('dashboard.jobs.all')}</option>
            {props.jobTypes.map((jt) => (
              <option key={jt} value={jt}>
                {jt}
              </option>
            ))}
          </select>
        </label>
      </div>
      {props.actionError && <Alert>{t(`errors.${props.actionError}`, t('errors.generic'))}</Alert>}
      {props.state === 'loading' && <Loading />}
      {props.state === 'error' && <LoadError code={props.errorCode} onRetry={props.onRetry} />}
      {props.state === 'ready' && props.jobs.length === 0 && <Empty>{t('dashboard.jobs.empty')}</Empty>}
      {props.state === 'ready' && props.jobs.length > 0 && (
        <Card className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead className="text-xs text-slate-500">
              <tr>
                <th>{t('dashboard.jobs.col.type')}</th>
                <th>{t('dashboard.jobs.col.status')}</th>
                <th>{t('dashboard.jobs.col.created')}</th>
                <th>{t('dashboard.jobs.col.cost')}</th>
                <th>{t('dashboard.jobs.col.actions')}</th>
              </tr>
            </thead>
            <tbody>
              {props.jobs.map((j) => (
                <tr key={j.id} className="border-t border-slate-200" data-testid="job-row">
                  <td className="py-1 pr-2">
                    <Link to={`/jobs/${j.id}`} className="underline">
                      {j.job_type}
                    </Link>{' '}
                    {j.data_origin === 'MOCK' && <MockBadge />}
                  </td>
                  <td className="py-1 pr-2" data-testid="job-status">
                    {t(`dashboard.jobs.status.${j.status}`, j.status)}
                  </td>
                  <td className="py-1 pr-2">{formatDateTime(j.created_at)}</td>
                  <td className="py-1 pr-2">{j.cost_accumulated_usd ? formatMoney(j.cost_accumulated_usd) : t('dashboard.unknown')}</td>
                  <td className="py-1 pr-2">
                    <JobActions job={j} onAction={props.onAction} confirm={props.confirm} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {props.total > props.jobs.length && (
            <p className="mt-2 text-xs text-slate-500">{t('dashboard.jobs.truncated', { shown: props.jobs.length, total: props.total })}</p>
          )}
        </Card>
      )}
      <Card className="space-y-2" data-testid="schedules">
        <h2 className="text-lg font-semibold">{t('dashboard.jobs.schedules')}</h2>
        {props.schedules.length === 0 ? (
          <Empty>{t('dashboard.jobs.noSchedules')}</Empty>
        ) : (
          <ul className="space-y-1 text-sm">
            {props.schedules.map((s) => (
              <li key={s.id} className="flex flex-wrap items-center gap-2" data-testid="schedule-row">
                <span className="font-medium">{s.name}</span>
                <span className="text-slate-500">
                  {s.job_type} · {s.cron_expr} ({s.timezone})
                </span>
                <span className="text-xs text-slate-500">
                  {t('dashboard.jobs.nextRun')}: {s.next_run_at ? formatDateTime(s.next_run_at) : t('dashboard.unknown')}
                </span>
                <label className="ml-auto flex items-center gap-1">
                  <input
                    type="checkbox"
                    checked={s.enabled}
                    onChange={(e) => props.onToggleSchedule(s.id, e.target.checked)}
                    data-testid="schedule-enabled"
                  />
                  {t('dashboard.jobs.enabled')}
                </label>
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    if (ask(t('dashboard.jobs.confirmDelete'))) props.onDeleteSchedule(s.id)
                  }}
                >
                  {t('dashboard.jobs.delete')}
                </Button>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  )
}
