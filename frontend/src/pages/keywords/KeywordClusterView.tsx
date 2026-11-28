// E3 màn hình 2 – Chi tiết cluster (T036, FR-009, FR-012…FR-015, FR-022…FR-025, FR-031): keyword + chỉ số (UNKNOWN khi không nguồn),
// intent + trạng thái, SERP quan sát, trang đối thủ, content gap, kênh, persona cụm, strategy, quyết định, theo dõi SERP. View thuần.
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import type { ClusterDecision, ClusterDetail, KeywordItem, KeywordMetric } from '@/api/types'
import { ExportCsvButton } from '@/components/ExportCsvButton'
import { MockBadge } from '@/components/MockBadge'
import { Button } from '@/components/ui/button'
import { Alert, Card, Input, Label } from '@/components/ui/form'
import { formatDateTime } from '@/i18n'
import { keywordsCsv } from '@/lib/exports'

export interface KeywordClusterViewProps {
  nicheId: string
  state: 'loading' | 'error' | 'ready'
  errorCode?: string
  cluster?: ClusterDetail
  decisionError: string | null
  onDecision: (decision: Exclude<ClusterDecision, 'CANDIDATE'>, reason: string) => void
  onWatch: (enabled: boolean) => void
  onAcknowledge: (version: number) => void
  onRetry: () => void
}

const DECISIONS: Exclude<ClusterDecision, 'CANDIDATE'>[] = ['SELECTED', 'WATCH', 'REJECTED']
const PERSONA_KEYS = ['goals', 'barriers', 'knowledge_level', 'typical_questions'] as const

function MetricCell({ m }: { m: KeywordMetric }) {
  const { t } = useTranslation()
  if (m.value == null || !m.source) {
    return (
      <span data-testid="metric-unknown" title={t('keywords.metrics.noSource')}>
        {t('keywords.unknown')}
      </span>
    )
  }
  return (
    <span title={`${m.source} · ${m.market ?? ''} · ${m.collected_at ?? ''}`}>
      {m.value} <span className="text-xs text-slate-500">({m.source})</span>
    </span>
  )
}

function KeywordRow({ k }: { k: KeywordItem }) {
  const { t } = useTranslation()
  const ev = k.evaluation
  return (
    <tr className="border-t border-slate-200 align-top" data-testid="keyword-row">
      <td className="py-1 pr-2">
        <div className="font-medium">{k.text}</div>
        <div className="text-xs text-slate-500">
          {k.origins.map((o) => `${t(`keywords.origin.${o.origin_type}`)}: ${o.label}`).join(' · ')}
        </div>
        {k.risk_flags.map((f) => (
          <span key={f} className="mr-1 rounded-full bg-amber-100 px-2 py-0.5 text-xs">
            {t(`keywords.flags.${f}`, f)}
          </span>
        ))}
      </td>
      <td className="py-1 pr-2 text-sm">
        {t(`keywords.intent.${k.intent}`)}
        <div className="text-xs text-slate-500" data-testid="intent-status">
          {t(`keywords.intentStatus.${k.intent_status}`)}
        </div>
      </td>
      <td className="py-1 pr-2 text-sm">{t(`keywords.length.${k.length_class}`)}</td>
      <td className="py-1 pr-2 text-sm">
        <MetricCell m={k.metrics.search_volume} />
      </td>
      <td className="py-1 pr-2 text-sm">
        <MetricCell m={k.metrics.cpc} />
      </td>
      <td className="py-1 pr-2 text-sm">
        <MetricCell m={k.metrics.keyword_difficulty} />
      </td>
      <td className="py-1 pr-2 text-sm">
        {ev?.opportunity_score ?? t('keywords.score.insufficient')}
        {ev && ev.missing.length > 0 && (
          <div className="text-xs text-slate-500">
            {t('keywords.score.missing')}: {ev.missing.map((m) => t(`keywords.criteria.${m}`, m)).join(', ')}
          </div>
        )}
      </td>
    </tr>
  )
}

function DecisionCard({ c, props }: { c: ClusterDetail; props: KeywordClusterViewProps }) {
  const { t } = useTranslation()
  const [decision, setDecision] = useState<Exclude<ClusterDecision, 'CANDIDATE'>>('WATCH')
  const [reason, setReason] = useState('')
  return (
    <Card className="space-y-2">
      <h2 className="text-lg font-semibold">{t('keywords.decision.title')}</h2>
      <p className="text-sm" data-testid="cluster-decision">
        {t(`keywords.decision.status.${c.decision_status}`)}
        {c.decision_reason && ` – ${c.decision_reason}`}
      </p>
      <form
        className="flex flex-wrap items-end gap-2"
        onSubmit={(e) => {
          e.preventDefault()
          if (reason.trim()) props.onDecision(decision, reason.trim())
        }}
      >
        <select
          className="rounded-md border border-slate-300 px-2 py-1 text-sm"
          value={decision}
          onChange={(e) => setDecision(e.target.value as Exclude<ClusterDecision, 'CANDIDATE'>)}
          data-testid="cluster-decision-select"
        >
          {DECISIONS.map((d) => (
            <option key={d} value={d}>
              {t(`keywords.decision.status.${d}`)}
            </option>
          ))}
        </select>
        <div className="grow space-y-1">
          <Label htmlFor="cluster-reason">{t('keywords.decision.reason')}</Label>
          <Input id="cluster-reason" value={reason} onChange={(e) => setReason(e.target.value)} />
        </div>
        <Button size="sm" type="submit" disabled={!reason.trim()}>
          {t('keywords.decision.save')}
        </Button>
      </form>
      {props.decisionError && <Alert>{t(`errors.${props.decisionError}`, t('errors.generic'))}</Alert>}
    </Card>
  )
}

export function KeywordClusterView(props: KeywordClusterViewProps) {
  const { t } = useTranslation()
  if (props.state === 'loading') return <p className="text-sm text-slate-500">{t('app.loading')}</p>
  if (props.state === 'error' || !props.cluster) {
    return (
      <Alert className="flex items-center justify-between gap-4">
        <span>{t(`errors.${props.errorCode ?? 'generic'}`, t('errors.generic'))}</span>
        <Button size="sm" variant="outline" onClick={props.onRetry}>
          {t('app.retry')}
        </Button>
      </Alert>
    )
  }
  const c = props.cluster
  const unacked = c.serp.filter((s) => s.version > 1 && !s.acknowledged_at)
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold">{c.name}</h1>
        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs">{t(`keywords.intent.${c.intent}`)}</span>
        {c.data_origin === 'MOCK' && <MockBadge />}
        <Link to={`/niches/${props.nicheId}/keywords`} className="ml-auto text-sm underline">
          {t('keywords.cluster.back')}
        </Link>
      </div>
      <Alert variant="info">{t('keywords.opportunity.disclaimer')}</Alert>
      <Card className="space-y-1">
        <p className="text-sm">
          {t('keywords.score.opportunity')}: <strong>{c.opportunity_score ?? t('keywords.score.insufficient')}</strong> ·{' '}
          {t('keywords.score.confidence')}: {c.confidence_score ?? t('discovery.unknown')}
        </p>
        <p className="text-xs text-slate-500">{t('keywords.metrics.note')}</p>
      </Card>

      <Card className="space-y-2 overflow-x-auto">
        <div className="flex items-center gap-2">
          <h2 className="text-lg font-semibold">{t('keywords.cluster.keywords')}</h2>
          <span className="ml-auto">
            <ExportCsvButton filename="keywords.csv" build={() => keywordsCsv(c.keywords, t)} disabled={c.keywords.length === 0} />
          </span>
        </div>
        <table className="w-full text-left">
          <thead className="text-xs text-slate-500">
            <tr>
              <th>{t('keywords.table.keyword')}</th>
              <th>{t('keywords.table.intent')}</th>
              <th>{t('keywords.table.length')}</th>
              <th>{t('keywords.table.volume')}</th>
              <th>{t('keywords.table.cpc')}</th>
              <th>{t('keywords.table.kd')}</th>
              <th>{t('keywords.score.opportunity')}</th>
            </tr>
          </thead>
          <tbody>
            {c.keywords.map((k) => (
              <KeywordRow key={k.keyword_id} k={k} />
            ))}
          </tbody>
        </table>
      </Card>

      <Card className="space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-lg font-semibold">{t('keywords.serp.title')}</h2>
          <label className="ml-auto flex items-center gap-2 text-sm">
            <input type="checkbox" checked={c.watch_enabled} onChange={(e) => props.onWatch(e.target.checked)} />
            {t('keywords.serp.watch')}
          </label>
        </div>
        {c.last_check_error && <Alert>{t('keywords.serp.checkError', { error: c.last_check_error })}</Alert>}
        {unacked.map((s) => (
          <Alert key={`${s.keyword_id}-${s.version}`} className="flex items-center justify-between gap-4">
            <span>{t('keywords.serp.changed', { version: s.version })}</span>
            <Button size="sm" variant="outline" onClick={() => props.onAcknowledge(s.version)}>
              {t('keywords.serp.acknowledge')}
            </Button>
          </Alert>
        ))}
        {c.serp.length === 0 ? (
          <p className="text-sm text-slate-500" data-testid="serp-unknown">
            {t('keywords.serp.none')}
          </p>
        ) : (
          c.serp
            .filter((s, i, arr) => arr.findIndex((x) => x.keyword_id === s.keyword_id) === i)
            .map((s) => (
              <div key={s.keyword_id} className="space-y-1">
                <p className="text-xs text-slate-500">
                  {c.keywords.find((k) => k.keyword_id === s.keyword_id)?.text} · {t('keywords.serp.version', { version: s.version })} ·{' '}
                  {formatDateTime(s.collected_at)}
                </p>
                <ol className="list-decimal pl-5 text-sm">
                  {s.results.map((r) => (
                    <li key={r.url}>
                      <a href={r.url} className="underline" rel="noreferrer noopener" target="_blank">
                        {r.domain}
                      </a>{' '}
                      <span className="text-xs text-slate-500">({t(`keywords.pageType.${r.page_type}`, r.page_type)})</span>
                    </li>
                  ))}
                </ol>
              </div>
            ))
        )}
        <p className="text-xs text-slate-500">{t('keywords.serp.note')}</p>
      </Card>

      <Card className="space-y-2">
        <h2 className="text-lg font-semibold">{t('keywords.gaps.title')}</h2>
        {c.content_gaps.status === 'UNKNOWN' ? (
          <p className="text-sm">
            {t('keywords.unknown')} – {t('keywords.gaps.unknown')}
          </p>
        ) : c.content_gaps.items.length === 0 ? (
          <p className="text-sm">{t('keywords.gaps.none')}</p>
        ) : (
          <ul className="list-disc pl-5 text-sm">
            {c.content_gaps.items.map((g) => (
              <li key={g.pain_point_id}>
                {g.title} <span className="text-xs text-slate-500">({t('keywords.gaps.checked', { n: g.checked_urls.length })})</span>
              </li>
            ))}
          </ul>
        )}
        {c.competitor_pages.length > 0 && (
          <ul className="space-y-1 text-xs text-slate-600">
            {c.competitor_pages.map((p) => (
              <li key={`${p.keyword_id}-${p.url}`}>
                <a href={p.url} className="underline" rel="noreferrer noopener" target="_blank">
                  {p.domain}
                </a>
                {p.excerpt && ` – ${p.excerpt}`}
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card className="space-y-2">
        <h2 className="text-lg font-semibold">{t('keywords.channels.title')}</h2>
        {c.channels.status === 'UNKNOWN' || c.channels.items.length === 0 ? (
          <p className="text-sm">{t('keywords.unknown')}</p>
        ) : (
          <ul className="list-disc pl-5 text-sm">
            {c.channels.items.map((ch) => (
              <li key={ch.domain}>
                {ch.domain} ({t(`keywords.pageType.${ch.kind}`, ch.kind)}) – {ch.evidence_urls.length}
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card className="space-y-2">
        <h2 className="text-lg font-semibold">{t('keywords.persona.title')}</h2>
        <dl className="grid gap-2 text-sm sm:grid-cols-2">
          {PERSONA_KEYS.map((k) => {
            const v = c.persona[k]
            return (
              <div key={k}>
                <dt className="text-slate-500">{t(`keywords.persona.${k}`)}</dt>
                <dd data-status={v?.status ?? 'UNKNOWN'}>
                  {v && v.status !== 'UNKNOWN' && v.value ? `${v.value} (${t('keywords.inferred')})`   : t('keywords.unknown')}
                </dd>
              </div>
            )
          })}
        </dl>
      </Card>

      <Card className="space-y-2">
        <h2 className="text-lg font-semibold">{t('keywords.strategy.title')}</h2>
        {c.strategy.status === 'INFERRED' ? (
          <div className="space-y-1 text-sm" data-testid="strategy">
            <p>
              {t('keywords.strategy.contentType')}: {t(`keywords.contentType.${c.strategy.content_type}`, c.strategy.content_type ?? '')}
            </p>
            <p>
              {t('keywords.strategy.angle')}: {c.strategy.angle}
            </p>
            <p className="text-xs text-slate-500">{t('keywords.strategy.note')}</p>
          </div>
        ) : (
          <p className="text-sm">{t('keywords.unknown')}</p>
        )}
      </Card>

      <DecisionCard c={c} props={props} />
    </div>
  )
}
