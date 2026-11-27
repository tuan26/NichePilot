// E3 màn hình 1 – Cluster keyword theo ngách (T036, FR-028, FR-021, FR-027): 2 danh sách, Opportunity/Confidence, intent, số keyword,
// long-tail, nhãn MOCK. View thuần; container ở NicheKeywordsPage. Chú thích "không phải dự báo traffic/doanh thu" luôn hiển thị.
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import type { ClusterItem, KeywordList } from '@/api/types'
import { MockBadge } from '@/components/MockBadge'
import { Button } from '@/components/ui/button'
import { Alert, Card } from '@/components/ui/form'

export interface NicheKeywordsViewProps {
  nicheId: string
  list: KeywordList
  state: 'loading' | 'error' | 'ready'
  errorCode?: string
  items: ClusterItem[]
  includeMock: boolean
  running: boolean
  runError: string | null
  runStarted: boolean
  onListChange: (list: KeywordList) => void
  onIncludeMockChange: (v: boolean) => void
  onRun: () => void
  onRetry: () => void
}

const LISTS: KeywordList[] = ['ranked', 'needs_research']

function ClusterRow({ c, nicheId }: { c: ClusterItem; nicheId: string }) {
  const { t } = useTranslation()
  return (
    <Card className="space-y-2" data-testid="cluster-row">
      <div className="flex flex-wrap items-center gap-2">
        <Link to={`/niches/${nicheId}/keywords/${c.cluster_id}`} className="font-semibold underline">
          {c.name}
        </Link>
        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs">{t(`keywords.intent.${c.intent}`)}</span>
        {c.data_origin === 'MOCK' && <MockBadge />}
        {c.serp_alert && <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs">{t('keywords.serp.alert')}</span>}
      </div>
      <p className="text-xs text-slate-500">
        {t('keywords.cluster.origin')}: {c.origin_label}
      </p>
      <dl className="grid gap-2 text-sm sm:grid-cols-4">
        <div>
          <dt className="text-slate-500">{t('keywords.score.opportunity')}</dt>
          <dd data-testid="cluster-opportunity">{c.opportunity_score ?? t('keywords.score.insufficient')}</dd>
        </div>
        <div>
          <dt className="text-slate-500">{t('keywords.score.confidence')}</dt>
          <dd>{c.confidence_score ?? t('discovery.unknown')}</dd>
        </div>
        <div>
          <dt className="text-slate-500">{t('keywords.cluster.keywords')}</dt>
          <dd>{t('keywords.cluster.counts', { total: c.keyword_count, longTail: c.long_tail_count })}</dd>
        </div>
        <div>
          <dt className="text-slate-500">{t('keywords.decision.title')}</dt>
          <dd>{t(`keywords.decision.status.${c.decision_status}`)}</dd>
        </div>
      </dl>
    </Card>
  )
}

export function NicheKeywordsView(props: NicheKeywordsViewProps) {
  const { t } = useTranslation()
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold">{t('keywords.title')}</h1>
          <Link to={`/niches/${props.nicheId}`} className="text-sm underline">
            {t('keywords.back')}
          </Link>
          <Button size="sm" className="ml-auto" disabled={props.running} onClick={props.onRun} data-testid="run-keywords">
            {t('keywords.run')}
          </Button>
        </div>
        <Alert variant="info">{t('keywords.opportunity.disclaimer')}</Alert>
        {props.runError && <Alert data-testid="run-error">{t(`errors.${props.runError}`, t('errors.generic'))}</Alert>}
        {props.runStarted && <Alert variant="info">{t('keywords.runStarted')}</Alert>}
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
            {t(`keywords.list.${l}`)}
          </Button>
        ))}
        <label className="ml-auto flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={props.includeMock}
            onChange={(e) => props.onIncludeMockChange(e.target.checked)}
            data-testid="keywords-include-mock"
          />
          {t('keywords.includeMock')}
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
      {props.state === 'ready' && props.items.length === 0 && <p className="text-sm text-slate-500">{t('keywords.empty')}</p>}
      {props.state === 'ready' && props.items.map((c) => <ClusterRow key={c.cluster_id} c={c} nicheId={props.nicheId} />)}
    </div>
  )
}
