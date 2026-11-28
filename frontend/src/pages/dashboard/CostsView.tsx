// E4 Chi phí (FR-016): hôm nay/tháng so với ngân sách, theo provider/model/loại job; REAL và MOCK tách riêng, MOCK không cộng vào chi phí thực.
import { useTranslation } from 'react-i18next'
import type { Budget, CostSummary } from '@/api/dashboard'
import { Card } from '@/components/ui/form'
import { formatMoney, formatNumber } from '@/i18n'
import { Empty, LoadError, Loading, type LoadState } from '@/pages/dashboard/common'

export interface CostsViewProps {
  state: LoadState
  errorCode?: string
  budget?: Budget
  real?: CostSummary
  mock?: CostSummary
  period: 'day' | 'month'
  onPeriodChange: (p: 'day' | 'month') => void
  onRetry: () => void
}

function Breakdown({ s, testId }: { s?: CostSummary; testId: string }) {
  const { t } = useTranslation()
  if (!s) return <Loading />
  return (
    <div className="space-y-2" data-testid={testId}>
      <p className="text-sm">
        {t('dashboard.costs.total')}: <strong>{formatMoney(s.total_usd)}</strong> · {t('dashboard.costs.calls')}: {formatNumber(s.call_count)}
      </p>
      {s.by_model.length === 0 ? (
        <Empty>{t('dashboard.costs.noUsage')}</Empty>
      ) : (
        <table className="w-full text-left text-sm">
          <thead className="text-xs text-slate-500">
            <tr>
              <th>{t('dashboard.costs.provider')}</th>
              <th>{t('dashboard.costs.model')}</th>
              <th>{t('dashboard.costs.tokens')}</th>
              <th>{t('dashboard.costs.cost')}</th>
            </tr>
          </thead>
          <tbody>
            {s.by_model.map((m) => (
              <tr key={`${m.provider}-${m.model}`} className="border-t border-slate-200">
                <td>{m.provider}</td>
                <td>{m.model}</td>
                <td>
                  {formatNumber(m.input_tokens)} / {formatNumber(m.output_tokens)}
                </td>
                <td>{formatMoney(m.cost_usd)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {s.by_job_type.length > 0 && (
        <ul className="text-xs text-slate-600">
          {s.by_job_type.map((j) => (
            <li key={j.job_type}>
              {j.job_type}: {formatMoney(j.cost_usd)} ({t('dashboard.costs.jobs', { n: j.job_count })})
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}

export function CostsView(props: CostsViewProps) {
  const { t } = useTranslation()
  const b = props.budget
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold">{t('dashboard.costs.title')}</h1>
        <div className="ml-auto flex gap-1" role="tablist">
          {(['day', 'month'] as const).map((p) => (
            <button
              key={p}
              type="button"
              role="tab"
              aria-selected={props.period === p}
              className={`rounded-md px-2 py-1 text-sm ${props.period === p ? 'bg-slate-900 text-white' : 'border border-slate-300'}`}
              onClick={() => props.onPeriodChange(p)}
            >
              {t(`dashboard.costs.period.${p}`)}
            </button>
          ))}
        </div>
      </div>
      {props.state === 'loading' && <Loading />}
      {props.state === 'error' && <LoadError code={props.errorCode} onRetry={props.onRetry} />}
      {props.state === 'ready' && b && (
        <Card className="space-y-1 text-sm" data-testid="budget">
          <h2 className="text-lg font-semibold">{t('dashboard.costs.budget')}</h2>
          <p>
            {t('dashboard.costs.today')}: {formatMoney(b.real.spent_today_usd)} / {formatMoney(b.limits.daily_usd)} ·{' '}
            {t('dashboard.costs.remaining')}: {formatMoney(b.real.remaining_today_usd)}
          </p>
          <p>
            {t('dashboard.costs.month')}: {formatMoney(b.real.spent_month_usd)} / {formatMoney(b.limits.monthly_usd)} ·{' '}
            {t('dashboard.costs.remaining')}: {formatMoney(b.real.remaining_month_usd)}
          </p>
          {b.real.warnings.map((w) => (
            <p key={w} className="text-amber-700" data-testid="budget-warning">
              {t(`dashboard.costs.warning.${w}`, w)}
            </p>
          ))}
          <p className="text-xs text-slate-500">{t('dashboard.costs.timezone', { tz: b.timezone })}</p>
        </Card>
      )}
      {props.state === 'ready' && (
        <div className="grid gap-4 md:grid-cols-2">
          <Card className="space-y-2">
            <h2 className="text-lg font-semibold">{t('dashboard.costs.real')}</h2>
            <Breakdown s={props.real} testId="costs-real" />
          </Card>
          <Card className="space-y-2">
            <h2 className="text-lg font-semibold">{t('dashboard.costs.mock')}</h2>
            <p className="text-xs text-slate-500">{t('dashboard.costs.mockNote')}</p>
            <Breakdown s={props.mock} testId="costs-mock" />
          </Card>
        </div>
      )}
    </div>
  )
}
