// Màn hình 1 – Danh sách lượt khám phá (T068, FR-026): view thuần (dễ kiểm thử), container ở DiscoveryRunsPage.
// Không có tùy chọn dùng nguồn chưa xác minh (quyết định A1). Dữ liệu MOCK luôn gắn nhãn.
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { RunAction } from '@/api/discovery'
import type { DiscoveryRun, DiscoveryRunCreate } from '@/api/types'
import { MockBadge } from '@/components/MockBadge'
import { Button } from '@/components/ui/button'
import { Alert, Card, Input, Label } from '@/components/ui/form'
import { formatDateTime } from '@/i18n'

export interface DiscoveryRunsViewProps {
  state: 'loading' | 'error' | 'ready'
  errorCode?: string
  runs: DiscoveryRun[]
  creating: boolean
  createError: string | null
  onCreate: (body: DiscoveryRunCreate) => void
  onAction: (jobId: string, action: RunAction) => void
  onRetry: () => void
}

const ACTIVE = new Set(['QUEUED', 'RUNNING', 'RETRY_SCHEDULED'])
const PAUSED = new Set(['PAUSED', 'PAUSED_BUDGET'])

function metric(run: DiscoveryRun, key: string): string {
  const v = run.metrics[key]
  return v === undefined || v === null ? '0' : String(v)
}

function RunRow({ run, onAction }: { run: DiscoveryRun; onAction: DiscoveryRunsViewProps['onAction'] }) {
  const { t } = useTranslation()
  const status = run.job.status
  return (
    <Card className="space-y-3" data-testid="run-row">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-semibold">{run.market}</span>
        <span className="text-sm text-slate-600">{run.seed_topic ?? t('discovery.runs.openDomain')}</span>
        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs">{t(`discovery.jobStatus.${status}`, status)}</span>
        {run.data_origin === 'MOCK' && <MockBadge />}
        <span className="ml-auto text-xs text-slate-500">{formatDateTime(run.created_at)}</span>
      </div>
      <dl className="grid gap-2 text-sm sm:grid-cols-2">
        <div>
          <dt className="text-slate-500">{t('discovery.runs.outcome')}</dt>
          <dd data-testid="run-outcome">
            {run.outcome ? t(`discovery.outcome.${run.outcome}`) : t('discovery.runs.inProgress')}
            {run.stop_reason && ` – ${t(`discovery.stopReason.${run.stop_reason}`)}`}
          </dd>
        </div>
        <div>
          <dt className="text-slate-500">{t('discovery.runs.pages')}</dt>
          <dd>
            {t('discovery.runs.pagesValue', {
              ok: metric(run, 'pages_succeeded'),
              skipped: metric(run, 'pages_skipped'),
              failed: metric(run, 'pages_failed'),
            })}
          </dd>
        </div>
        <div>
          <dt className="text-slate-500">{t('discovery.runs.candidates')}</dt>
          <dd>{metric(run, 'candidates')}</dd>
        </div>
        <div>
          <dt className="text-slate-500">{t('discovery.runs.cost')}</dt>
          <dd>
            <span data-testid="run-cost-real">{t('discovery.runs.costReal', { usd: metric(run, 'cost_real_usd') })}</span>
            {' · '}
            <span data-testid="run-cost-mock">{t('discovery.runs.costMock', { usd: metric(run, 'cost_mock_usd') })}</span>
          </dd>
        </div>
        <div className="sm:col-span-2">
          <dt className="text-slate-500">{t('discovery.runs.sources')}</dt>
          <dd>{run.sources.map((s) => s.source_key).join(', ') || t('discovery.runs.noSources')}</dd>
        </div>
      </dl>
      <div className="flex gap-2">
        {ACTIVE.has(status) && (
          <Button size="sm" variant="outline" onClick={() => onAction(run.job.job_id, 'pause')}>
            {t('discovery.runs.pause')}
          </Button>
        )}
        {PAUSED.has(status) && (
          <Button size="sm" variant="outline" onClick={() => onAction(run.job.job_id, 'resume')}>
            {t('discovery.runs.resume')}
          </Button>
        )}
        {(ACTIVE.has(status) || PAUSED.has(status)) && (
          <Button size="sm" variant="outline" onClick={() => onAction(run.job.job_id, 'cancel')}>
            {t('discovery.runs.cancel')}
          </Button>
        )}
      </div>
    </Card>
  )
}

export function DiscoveryRunsView(props: DiscoveryRunsViewProps) {
  const { t } = useTranslation()
  const [market, setMarket] = useState('US')
  const [seedTopic, setSeedTopic] = useState('')
  const [maxCandidates, setMaxCandidates] = useState(20)
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">{t('discovery.runs.title')}</h1>
        <p className="mt-1 text-sm text-slate-600">{t('discovery.runs.description')}</p>
      </div>
      <Card>
        <form
          className="grid gap-4 sm:grid-cols-4"
          onSubmit={(e) => {
            e.preventDefault()
            props.onCreate({ market, seed_topic: seedTopic.trim() || null, max_candidates: maxCandidates })
          }}
        >
          <div className="space-y-1">
            <Label htmlFor="run-market">{t('discovery.runs.market')}</Label>
            <Input id="run-market" value={market} maxLength={2} onChange={(e) => setMarket(e.target.value.toUpperCase())} />
          </div>
          <div className="space-y-1 sm:col-span-2">
            <Label htmlFor="run-seed">{t('discovery.runs.seedTopic')}</Label>
            <Input id="run-seed" value={seedTopic} placeholder={t('discovery.runs.seedPlaceholder')} onChange={(e) => setSeedTopic(e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label htmlFor="run-max">{t('discovery.runs.maxCandidates')}</Label>
            <Input id="run-max" type="number" min={1} max={50} value={maxCandidates} onChange={(e) => setMaxCandidates(Number(e.target.value))} />
          </div>
          <div className="sm:col-span-4 flex items-center gap-3">
            <Button type="submit" disabled={props.creating}>
              {t('discovery.runs.start')}
            </Button>
            <span className="text-xs text-slate-500">{t('discovery.runs.allowedOnly')}</span>
          </div>
        </form>
        {props.createError && (
          <Alert className="mt-4" data-testid="create-error">
            {t(`errors.${props.createError}`, t('errors.generic'))}
          </Alert>
        )}
      </Card>

      {props.state === 'loading' && <p className="text-sm text-slate-500">{t('app.loading')}</p>}
      {props.state === 'error' && (
        <Alert className="flex items-center justify-between gap-4">
          <span>{t(`errors.${props.errorCode ?? 'generic'}`, t('errors.generic'))}</span>
          <Button size="sm" variant="outline" onClick={props.onRetry}>
            {t('app.retry')}
          </Button>
        </Alert>
      )}
      {props.state === 'ready' && props.runs.length === 0 && (
        <p className="text-sm text-slate-500" data-testid="runs-empty">
          {t('discovery.runs.empty')}
        </p>
      )}
      {props.state === 'ready' && props.runs.map((run) => <RunRow key={run.id} run={run} onAction={props.onAction} />)}
    </div>
  )
}
