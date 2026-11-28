// E4 trang Product Discovery / Keyword Research toàn cục (FR-009…FR-012): ngách kèm tóm tắt E2 hoặc E3, liên kết tới trang theo ngách.
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import type { ResearchNiche } from '@/api/dashboard'
import { MockBadge } from '@/components/MockBadge'
import { Card } from '@/components/ui/form'
import { formatNumber } from '@/i18n'
import { Empty, LoadError, Loading, type LoadState, MockToggle, Score } from '@/pages/dashboard/common'

export interface ResearchNichesViewProps {
  mode: 'products' | 'keywords'
  state: LoadState
  errorCode?: string
  items: ResearchNiche[]
  includeMock: boolean
  onIncludeMockChange: (v: boolean) => void
  onRetry: () => void
}

function Summary({ n, mode }: { n: ResearchNiche; mode: 'products' | 'keywords' }) {
  const { t } = useTranslation()
  if (mode === 'products') {
    if (!n.products.has_run) return <span data-testid="not-run">{t('dashboard.research.notRunProducts')}</span>
    return (
      <span data-testid="summary">
        {t('dashboard.research.productsSummary', { total: formatNumber(n.products.total), ready: formatNumber(n.products.ready_to_promote) })}
      </span>
    )
  }
  if (!n.keywords.has_run) return <span data-testid="not-run">{t('dashboard.research.notRunKeywords')}</span>
  const b = n.keywords.best_cluster
  return (
    <span data-testid="summary">
      {t('dashboard.research.keywordsSummary', {
        total: formatNumber(n.keywords.total),
        clusters: formatNumber(n.keywords.clusters),
        longTail: formatNumber(n.keywords.long_tail),
      })}
      {b && (
        <>
          {' · '}
          {t('dashboard.research.bestCluster')}: {b.name} (<Score opportunity={b.opportunity_score} confidence={b.confidence_score} />)
        </>
      )}
    </span>
  )
}

export function ResearchNichesView(props: ResearchNichesViewProps) {
  const { t } = useTranslation()
  const shown = props.items.filter((n) => n.eligible || (props.mode === 'products' ? n.products.has_run : n.keywords.has_run))
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold">{t(`dashboard.research.title.${props.mode}`)}</h1>
        <div className="ml-auto">
          <MockToggle checked={props.includeMock} onChange={props.onIncludeMockChange} />
        </div>
      </div>
      <p className="text-sm text-slate-600">{t(`dashboard.research.description.${props.mode}`)}</p>
      {props.state === 'loading' && <Loading />}
      {props.state === 'error' && <LoadError code={props.errorCode} onRetry={props.onRetry} />}
      {props.state === 'ready' && shown.length === 0 && (
        <Empty>
          {t('dashboard.research.empty')}{' '}
          <Link to="/niches" className="underline">
            {t('dashboard.research.openNiches')}
          </Link>
        </Empty>
      )}
      {props.state === 'ready' &&
        shown.map((n) => (
          <Card key={n.niche_id} className="space-y-1" data-testid="research-row">
            <div className="flex flex-wrap items-center gap-2">
              <Link to={`/niches/${n.niche_id}/${props.mode}`} className="font-semibold underline">
                {n.name}
              </Link>
              <span className="text-xs text-slate-500">{n.country}</span>
              {n.data_origin === 'MOCK' && <MockBadge />}
            </div>
            <p className="text-sm">
              <Score opportunity={n.opportunity_score} confidence={n.confidence_score} />
            </p>
            <p className="text-sm">
              <Summary n={n} mode={props.mode} />
            </p>
          </Card>
        ))}
    </div>
  )
}
