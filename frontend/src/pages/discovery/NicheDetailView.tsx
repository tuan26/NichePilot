// Màn hình 3 – Chi tiết ngách (T084, FR-026, FR-013e): pain point, persona, giải pháp/khoảng trống, đối thủ, bằng chứng + nguồn.
// View thuần (dễ kiểm thử); container ở NicheDetailPage. MOCK luôn gắn nhãn; UNKNOWN hiển thị rõ, không suy diễn giá trị.
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { Evaluation, Finding, NicheDetail, SimilarityPair } from '@/api/types'
import { MockBadge } from '@/components/MockBadge'
import { Button } from '@/components/ui/button'
import { Alert, Card, Input, Label } from '@/components/ui/form'
import { formatDateTime } from '@/i18n'

export interface NicheDetailViewProps {
  state: 'loading' | 'error' | 'ready'
  errorCode?: string
  niche?: NicheDetail
  erasing: boolean
  eraseError: string | null
  confirmEvidenceId: string | null
  onAskErase: (evidenceId: string) => void
  onConfirmErase: (evidenceId: string, reason: string, scope: 'EVIDENCE' | 'SOURCE') => void
  onCancelErase: () => void
  onRetry: () => void
  onResolveDuplicate?: (pair: SimilarityPair, status: 'CONFIRMED_DUPLICATE' | 'NOT_DUPLICATE', keep?: string) => void
  onDecision?: (decision: string, reason: string) => void
  decisionError?: string | null
}

const PERSONA = ['segment', 'context', 'goals', 'obstacles', 'ability_to_pay']
const FINDINGS = ['CURRENT_SOLUTIONS', 'MARKET_GAPS', 'POTENTIAL_PRODUCTS', 'MONETIZATION', 'CHANNELS', 'RISKS']

function show(value: unknown): string {
  if (value === null || value === undefined) return 'UNKNOWN'
  if (Array.isArray(value)) return value.map(show).join('; ')
  if (typeof value === 'object') return JSON.stringify(value)
  return String(value)
}

function StatusChip({ status }: { status: string }) {
  const { t } = useTranslation()
  return (
    <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs" data-status={status}>
      {t(`discovery.verification.${status}`, status)}
    </span>
  )
}

function FindingValue({ f }: { f: Finding }) {
  const { t } = useTranslation()
  if (f.status === 'UNKNOWN') return <span className="text-slate-500">{t('discovery.unknown')}</span>
  if (f.status === 'CONFLICTING' && Array.isArray(f.value)) {
    return (
      <ul className="list-disc pl-5">
        {(f.value as { value: unknown; evidence_ids: string[] }[]).map((v, i) => (
          <li key={i}>{show(v.value)}</li>
        ))}
      </ul>
    )
  }
  return <span>{show(f.value)}</span>
}

function FindingRow({ label, f }: { label: string; f: Finding | undefined }) {
  const finding = f ?? { value: null, status: 'UNKNOWN' as const, evidence_ids: [] }
  return (
    <div className="grid gap-1 sm:grid-cols-[12rem_1fr_auto] sm:items-start">
      <dt className="text-slate-500">{label}</dt>
      <dd>
        <FindingValue f={finding} />
      </dd>
      <dd>
        <StatusChip status={finding.status} />
      </dd>
    </div>
  )
}

const CRITERIA = ['problem_severity', 'monetization', 'market_gap', 'reachability', 'competition_opportunity', 'demand_stability']

function ScoringCard({ ev, n }: { ev: Evaluation | null; n: NicheDetail }) {
  const { t } = useTranslation()
  return (
    <Card className="space-y-3" data-testid="scoring">
      <h2 className="text-lg font-semibold">{t('discovery.ranking.scoring')}</h2>
      <Alert variant="info">{t('discovery.opportunity.disclaimer')}</Alert>
      {!ev ? (
        <p className="text-sm text-slate-500">{t('discovery.unknown')}</p>
      ) : (
        <>
          <dl className="grid gap-2 text-sm sm:grid-cols-3">
            <div>
              <dt className="text-slate-500">{t('discovery.ranking.opportunity')}</dt>
              <dd>{ev.opportunity_score ?? t('discovery.ranking.insufficientScoring')}</dd>
            </div>
            <div>
              <dt className="text-slate-500">{t('discovery.ranking.confidence')}</dt>
              <dd>{ev.confidence_score}</dd>
            </div>
            <div>
              <dt className="text-slate-500">{t('discovery.ranking.coverage')}</dt>
              <dd>{ev.coverage}%</dd>
            </div>
          </dl>
          <p className="text-xs text-slate-500">
            {t('discovery.ranking.weightsVersion', { v: ev.weights_version })}
            {ev.computed_without_ai && ` · ${t('discovery.ranking.computedWithoutAi')}`}
          </p>
          <ul className="space-y-1 text-sm">
            {CRITERIA.map((k) => {
              const c = ev.criteria[k]
              return (
                <li key={k} className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">{t(`discovery.ranking.criteria.${k}`)}</span>
                  <span>{c?.score ?? t('discovery.unknown')}</span>
                  <span className="text-xs text-slate-500">{t('discovery.ranking.weight', { w: c?.weight ?? 0 })}</span>
                  {c && <StatusChip status={c.status} />}
                  {c?.reason && <span className="text-slate-600">– {c.reason}</span>}
                </li>
              )
            })}
          </ul>
        </>
      )}
      <p className="text-sm">
        {t('discovery.ranking.recommendation')}: {t(`discovery.ranking.rec.${n.ai_recommendation}`)}
        {n.ai_recommendation_reason ? ` – ${n.ai_recommendation_reason}` : ''}
      </p>
    </Card>
  )
}

function DuplicatesCard({ n, props }: { n: NicheDetail; props: NicheDetailViewProps }) {
  const { t } = useTranslation()
  const pairs = n.possible_duplicates ?? []
  if (pairs.length === 0) return null
  return (
    <Alert variant="warning" data-testid="possible-duplicates">
      <p className="font-medium">{t('discovery.dedup.title')}</p>
      <ul className="mt-2 space-y-2">
        {pairs.map((p) => {
          const otherName = p.niche_a_id === n.id ? p.niche_b_name : p.niche_a_name
          return (
            <li key={p.id} className="flex flex-wrap items-center gap-2">
              <span>{t('discovery.dedup.pair', { name: otherName ?? '', score: p.score })}</span>
              <Button size="sm" variant="outline" onClick={() => props.onResolveDuplicate?.(p, 'CONFIRMED_DUPLICATE', n.id)}>
                {t('discovery.dedup.mergeHere')}
              </Button>
              <Button size="sm" variant="outline" onClick={() => props.onResolveDuplicate?.(p, 'NOT_DUPLICATE')}>
                {t('discovery.dedup.notDuplicate')}
              </Button>
            </li>
          )
        })}
      </ul>
    </Alert>
  )
}

const DECISIONS = ['WATCH', 'PURSUE', 'REJECTED', 'HIDDEN', 'CANDIDATE']

function DecisionCard({ n, props }: { n: NicheDetail; props: NicheDetailViewProps }) {
  const { t } = useTranslation()
  const [decision, setDecision] = useState(n.decision_status === 'CANDIDATE' ? 'WATCH' : n.decision_status)
  const [reason, setReason] = useState('')
  return (
    <Card className="space-y-2" data-testid="decision">
      <h2 className="text-lg font-semibold">{t('discovery.decision.title')}</h2>
      <p className="text-sm">
        {t('discovery.decision.current')}: <strong>{t(`discovery.decision.status.${n.decision_status}`)}</strong>
      </p>
      {props.decisionError && <Alert>{t(`errors.${props.decisionError}`, t('errors.generic'))}</Alert>}
      <form
        className="flex flex-wrap items-end gap-2"
        onSubmit={(e) => {
          e.preventDefault()
          props.onDecision?.(decision, reason.trim())
        }}
      >
        <div className="space-y-1">
          <Label htmlFor="decision">{t('discovery.decision.choose')}</Label>
          <select id="decision" value={decision} onChange={(e) => setDecision(e.target.value)}>
            {DECISIONS.map((d) => (
              <option key={d} value={d}>
                {t(`discovery.decision.status.${d}`)}
              </option>
            ))}
          </select>
        </div>
        <div className="min-w-64 flex-1 space-y-1">
          <Label htmlFor="decision-reason">{t('discovery.decision.reason')}</Label>
          <Input id="decision-reason" value={reason} maxLength={2000} onChange={(e) => setReason(e.target.value)} />
        </div>
        <Button size="sm" type="submit" disabled={decision !== 'CANDIDATE' && reason.trim().length < 3}>
          {t('discovery.decision.save')}
        </Button>
      </form>
      <p className="text-xs text-slate-500">{t('discovery.decision.hint')}</p>
    </Card>
  )
}

function EraseConfirm({ id, props }: { id: string; props: NicheDetailViewProps }) {
  const { t } = useTranslation()
  const [reason, setReason] = useState('')
  const [scope, setScope] = useState<'EVIDENCE' | 'SOURCE'>('EVIDENCE')
  return (
    <form
      data-testid="erase-confirm"
      className="mt-3 space-y-2 rounded-md border border-red-200 bg-red-50 p-3 text-sm"
      onSubmit={(e) => {
        e.preventDefault()
        props.onConfirmErase(id, reason.trim(), scope)
      }}
    >
      <p>{t('discovery.niche.eraseWarning')}</p>
      <Label htmlFor={`reason-${id}`}>{t('discovery.niche.eraseReason')}</Label>
      <Input id={`reason-${id}`} value={reason} minLength={3} maxLength={500} required onChange={(e) => setReason(e.target.value)} />
      <label className="flex items-center gap-2">
        <input type="checkbox" checked={scope === 'SOURCE'} onChange={(e) => setScope(e.target.checked ? 'SOURCE' : 'EVIDENCE')} />
        {t('discovery.niche.eraseWholeSource')}
      </label>
      <div className="flex gap-2">
        <Button size="sm" type="submit" disabled={props.erasing || reason.trim().length < 3}>
          {t('discovery.niche.eraseConfirm')}
        </Button>
        <Button size="sm" variant="outline" type="button" onClick={props.onCancelErase}>
          {t('discovery.niche.eraseCancel')}
        </Button>
      </div>
    </form>
  )
}

export function NicheDetailView(props: NicheDetailViewProps) {
  const { t } = useTranslation()
  if (props.state === 'loading') return <p className="text-sm text-slate-500">{t('app.loading')}</p>
  if (props.state === 'error' || !props.niche) {
    return (
      <Alert className="flex items-center justify-between gap-4">
        <span>{t(`errors.${props.errorCode ?? 'generic'}`, t('errors.generic'))}</span>
        <Button size="sm" variant="outline" onClick={props.onRetry}>
          {t('app.retry')}
        </Button>
      </Alert>
    )
  }
  const n = props.niche
  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-2xl font-semibold">{n.name}</h1>
          {n.data_origin === 'MOCK' && <MockBadge />}
        </div>
        <p className="text-sm text-slate-600">
          {n.micro_niche} · {n.country} · {n.customer_group}
        </p>
        <div className="flex flex-wrap gap-2 text-xs">
          <span className="rounded-full bg-slate-100 px-2 py-0.5" data-testid="evidence-status">
            {t(`discovery.evidenceStatus.${n.evidence_status}`)}
          </span>
          <span className="rounded-full bg-slate-100 px-2 py-0.5">{t(`discovery.monetization.${n.monetization_status}`)}</span>
        </div>
        <Alert variant="info">{t(n.disclaimer_key)}</Alert>
      </div>

      <DuplicatesCard n={n} props={props} />
      <ScoringCard ev={n.latest_evaluation} n={n} />
      <DecisionCard n={n} props={props} />

      <Card className="space-y-3">
        <h2 className="text-lg font-semibold">{t('discovery.niche.painPoints')}</h2>
        {n.pain_points.length === 0 ? (
          <p className="text-sm text-slate-500">{t('discovery.niche.noPainPoints')}</p>
        ) : (
          <ul className="space-y-2">
            {n.pain_points.map((p) => (
              <li key={p.id} className="text-sm">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-medium">{p.title}</span>
                  <StatusChip status={p.status} />
                  <span className="text-xs text-slate-500">
                    {t('discovery.niche.severity', { value: p.severity ?? 'UNKNOWN' })} ·{' '}
                    {t('discovery.niche.evidenceCount', { count: p.evidence_count })}
                  </span>
                </div>
                {p.description && <p className="text-slate-600">{p.description}</p>}
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card className="space-y-3">
        <h2 className="text-lg font-semibold">{t('discovery.niche.persona')}</h2>
        <dl className="space-y-2 text-sm">
          {PERSONA.map((a) => (
            <FindingRow key={a} label={t(`discovery.persona.${a}`)} f={n.persona[a]} />
          ))}
        </dl>
      </Card>

      <Card className="space-y-3">
        <h2 className="text-lg font-semibold">{t('discovery.niche.findings')}</h2>
        <dl className="space-y-2 text-sm">
          {FINDINGS.map((f) => (
            <FindingRow key={f} label={t(`discovery.finding.${f}`)} f={n.findings[f]} />
          ))}
        </dl>
        <h3 className="font-medium">{t('discovery.niche.competitors')}</h3>
        {n.competitors.length === 0 ? (
          <p className="text-sm text-slate-500">{t('discovery.unknown')}</p>
        ) : (
          <ul className="list-disc pl-5 text-sm">
            {n.competitors.map((c) => (
              <li key={c.name}>
                {c.name} ({t(`discovery.competitorKind.${c.kind}`)})
                {c.weaknesses.length > 0 && ` – ${c.weaknesses.join(', ')}`}
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card className="space-y-3">
        <h2 className="text-lg font-semibold">{t('discovery.niche.evidence')}</h2>
        {props.eraseError && (
          <Alert data-testid="erase-error">{t(`errors.${props.eraseError}`, t('errors.generic'))}</Alert>
        )}
        {n.evidence.length === 0 ? (
          <p className="text-sm text-slate-500">{t('discovery.niche.noEvidence')}</p>
        ) : (
          <ul className="space-y-3">
            {n.evidence.map((e) => (
              <li key={e.id} className="rounded-md border border-slate-200 p-3 text-sm" data-testid="evidence-item">
                <blockquote className="text-slate-800">“{e.excerpt}”</blockquote>
                <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                  <a href={e.source_url} target="_blank" rel="noreferrer noopener" className="underline">
                    {e.source_url}
                  </a>
                  <span>{t('discovery.niche.collectedAt', { at: formatDateTime(e.collected_at) })}</span>
                  {e.policy_verified_at && (
                    <span>{t('discovery.niche.policyVerifiedAt', { date: e.policy_verified_at })}</span>
                  )}
                  <StatusChip status={e.verification_status} />
                  {e.counted_for_threshold && <span>{t('discovery.niche.counted')}</span>}
                  {e.data_origin === 'MOCK' && <MockBadge />}
                  <Button
                    size="sm"
                    variant="outline"
                    data-testid={`erase-${e.id}`}
                    disabled={props.erasing}
                    onClick={() => props.onAskErase(e.id)}
                  >
                    {t('discovery.niche.erase')}
                  </Button>
                </div>
                {props.confirmEvidenceId === e.id && <EraseConfirm id={e.id} props={props} />}
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  )
}
