// E4 Tổng quan (FR-006…FR-008, FR-012): bộ đếm ngách/sản phẩm/keyword/job, chi phí REAL/MOCK so với ngân sách, ngách hàng đầu kèm Confidence.
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import type { Budget, Overview } from '@/api/dashboard'
import { MockBadge } from '@/components/MockBadge'
import { Card } from '@/components/ui/form'
import { formatDateTime, formatMoney, formatNumber } from '@/i18n'
import { Empty, LoadError, Loading, type LoadState, MockToggle, Score } from '@/pages/dashboard/common'

export interface OverviewViewProps {
  state: LoadState
  errorCode?: string
  data?: Overview
  budget?: Budget
  includeMock: boolean
  onIncludeMockChange: (v: boolean) => void
  onRetry: () => void
}

function Stat({ label, value, testId }: { label: string; value: string; testId: string }) {
  return (
    <div>
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd className="text-xl font-semibold" data-testid={testId}>
        {value}
      </dd>
    </div>
  )
}

export function OverviewView(props: OverviewViewProps) {
  const { t } = useTranslation()
  const d = props.data
  const running = d ? (d.jobs.by_status.RUNNING ?? 0) + (d.jobs.by_status.QUEUED ?? 0) : 0
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold">{t('dashboard.overview.title')}</h1>
        <div className="ml-auto">
          <MockToggle checked={props.includeMock} onChange={props.onIncludeMockChange} />
        </div>
      </div>
      {props.state === 'loading' && <Loading />}
      {props.state === 'error' && <LoadError code={props.errorCode} onRetry={props.onRetry} />}
      {props.state === 'ready' && d && (
        <>
          <Card>
            <dl className="grid gap-4 sm:grid-cols-4">
              <Stat label={t('dashboard.overview.niches')} value={formatNumber(d.niches.total)} testId="stat-niches" />
              <Stat
                label={t('dashboard.overview.products')}
                value={t('dashboard.overview.productsValue', { total: formatNumber(d.products.total), ready: formatNumber(d.products.ready_to_promote) })}
                testId="stat-products"
              />
              <Stat
                label={t('dashboard.overview.keywords')}
                value={t('dashboard.overview.keywordsValue', { total: formatNumber(d.keywords.total), clusters: formatNumber(d.keywords.clusters) })}
                testId="stat-keywords"
              />
              <Stat
                label={t('dashboard.overview.jobs')}
                value={t('dashboard.overview.jobsValue', { running: formatNumber(running), failed: formatNumber(d.jobs.failed_7d) })}
                testId="stat-jobs"
              />
            </dl>
            {d.niches.total === 0 && (
              <Empty>
                {t('dashboard.overview.emptyNiches')}{' '}
                <Link to="/discovery/runs" className="underline">
                  {t('dashboard.overview.startDiscovery')}
                </Link>
              </Empty>
            )}
          </Card>
          <Card className="space-y-2" data-testid="overview-costs">
            <h2 className="text-lg font-semibold">{t('dashboard.costs.title')}</h2>
            {props.budget ? (
              <dl className="grid gap-2 text-sm sm:grid-cols-2">
                <div>
                  <dt className="text-slate-500">{t('dashboard.costs.today')}</dt>
                  <dd data-testid="cost-today-real">
                    {formatMoney(props.budget.real.spent_today_usd)} / {formatMoney(props.budget.limits.daily_usd)}
                  </dd>
                </div>
                <div>
                  <dt className="text-slate-500">{t('dashboard.costs.month')}</dt>
                  <dd>
                    {formatMoney(props.budget.real.spent_month_usd)} / {formatMoney(props.budget.limits.monthly_usd)}
                  </dd>
                </div>
                <div className="sm:col-span-2 text-xs text-slate-500" data-testid="cost-mock">
                  {t('dashboard.costs.mockSeparate', { amount: formatMoney(props.budget.mock.spent_month_usd) })}
                </div>
              </dl>
            ) : (
              <Loading />
            )}
            <Link to="/costs" className="text-sm underline">
              {t('dashboard.costs.open')}
            </Link>
          </Card>
          <Card className="space-y-2">
            <h2 className="text-lg font-semibold">{t('dashboard.overview.topNiches')}</h2>
            {d.top_niches.length === 0 ? (
              <Empty>{t('dashboard.overview.noTopNiches')}</Empty>
            ) : (
              <ol className="space-y-1 text-sm">
                {d.top_niches.map((n) => (
                  <li key={n.niche_id} className="flex flex-wrap items-center gap-2" data-testid="top-niche">
                    <Link to={`/niches/${n.niche_id}`} className="font-medium underline">
                      {n.name}
                    </Link>
                    {n.data_origin === 'MOCK' && <MockBadge />}
                    <Score opportunity={n.opportunity_score} confidence={n.confidence_score} />
                  </li>
                ))}
              </ol>
            )}
            <p className="text-xs text-slate-500">{t('dashboard.score.disclaimer')}</p>
          </Card>
          <p className="text-xs text-slate-500">{t('dashboard.updatedAt', { time: formatDateTime(d.generated_at) })}</p>
        </>
      )}
    </div>
  )
}
