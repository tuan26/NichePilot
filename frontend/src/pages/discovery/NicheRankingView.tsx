// Màn hình 2 – Bảng xếp hạng ngách (T099, FR-024, FR-026, FR-019c): 3 danh sách theo scoring-rubric §4. View thuần; container ở
// NicheRankingPage. Opportunity là điểm ưu tiên nghiên cứu, không phải dự báo doanh thu (chú thích luôn hiển thị).
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import type { NicheSummary, RankingList } from '@/api/types'
import { MockBadge } from '@/components/MockBadge'
import { Button } from '@/components/ui/button'
import { Alert, Card } from '@/components/ui/form'

export interface NicheRankingViewProps {
  list: RankingList
  state: 'loading' | 'error' | 'ready'
  errorCode?: string
  items: NicheSummary[]
  includeMock: boolean
  onListChange: (list: RankingList) => void
  onIncludeMockChange: (v: boolean) => void
  onRetry: () => void
}

const LISTS: RankingList[] = ['research', 'affiliate', 'needs_research']

function Row({ n }: { n: NicheSummary }) {
  const { t } = useTranslation()
  const summary = Object.entries(n.verification_summary)
    .filter(([, v]) => v > 0)
    .map(([k, v]) => `${k}: ${v}`)
    .join(' · ')
  return (
    <Card className="space-y-2" data-testid="ranking-row">
      <div className="flex flex-wrap items-center gap-2">
        <Link to={`/niches/${n.id}`} className="font-semibold underline">
          {n.name}
        </Link>
        <span className="text-sm text-slate-600">{n.country}</span>
        {n.data_origin === 'MOCK' && <MockBadge />}
        {n.has_possible_duplicate && (
          <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs">{t('discovery.ranking.possibleDuplicate')}</span>
        )}
      </div>
      <dl className="grid gap-2 text-sm sm:grid-cols-4">
        <div>
          <dt className="text-slate-500">{t('discovery.ranking.opportunity')}</dt>
          <dd data-testid="opportunity">
            {n.opportunity_score === null ? t('discovery.ranking.insufficientScoring') : n.opportunity_score}
          </dd>
        </div>
        <div>
          <dt className="text-slate-500">{t('discovery.ranking.confidence')}</dt>
          <dd>{n.confidence_score ?? t('discovery.unknown')}</dd>
        </div>
        <div>
          <dt className="text-slate-500">{t('discovery.ranking.coverage')}</dt>
          <dd>{n.coverage === null ? t('discovery.unknown') : `${n.coverage}%`}</dd>
        </div>
        <div>
          <dt className="text-slate-500">{t('discovery.ranking.monetization')}</dt>
          <dd>{t(`discovery.monetization.${n.monetization_status}`)}</dd>
        </div>
      </dl>
      <p className="text-xs text-slate-500">
        {t(`discovery.evidenceStatus.${n.evidence_status}`)} · {summary}
      </p>
    </Card>
  )
}

export function NicheRankingView(props: NicheRankingViewProps) {
  const { t } = useTranslation()
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold">{t('discovery.ranking.title')}</h1>
        <Alert variant="info" className="mt-2">
          {t('discovery.opportunity.disclaimer')}
        </Alert>
      </div>
      <div className="flex flex-wrap items-center gap-2" role="tablist">
        {LISTS.map((l) => (
          <Button
            key={l}
            size="sm"
            role="tab"
            aria-selected={props.list === l}
            variant={props.list === l ? 'default' : 'outline'}
            onClick={() => props.onListChange(l)}
          >
            {t(`discovery.ranking.list.${l}`)}
          </Button>
        ))}
        <label className="ml-auto flex items-center gap-2 text-sm">
          <input type="checkbox" checked={props.includeMock} onChange={(e) => props.onIncludeMockChange(e.target.checked)} />
          {t('discovery.ranking.includeMock')}
        </label>
      </div>
      {props.state === 'loading' && <p className="text-sm text-slate-500">{t('app.loading')}</p>}
      {props.state === 'error' && (
        <Alert className="flex items-center justify-between gap-4">
          <span>{t(`errors.${props.errorCode ?? 'generic'}`, t('errors.generic'))}</span>
          <Button size="sm" variant="outline" onClick={props.onRetry}>
            {t('app.retry')}
          </Button>
        </Alert>
      )}
      {props.state === 'ready' && props.items.length === 0 && (
        <p className="text-sm text-slate-500">{t('discovery.ranking.empty')}</p>
      )}
      {props.state === 'ready' && props.items.map((n) => <Row key={n.id} n={n} />)}
    </div>
  )
}
