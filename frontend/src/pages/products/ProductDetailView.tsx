// E2 màn hình 2 – Chi tiết sản phẩm (T054, T059; FR-007, FR-008, FR-026, FR-033, FR-036, FR-040): thuộc tính kèm trạng thái xác minh
// và nguồn (CONFLICTING hiển thị mọi giá trị), chương trình affiliate, điểm theo tiêu chí, quyết định, theo dõi điều khoản.
// View thuần; container ở ProductDetailPage. Không có thao tác đăng ký affiliate (FR-025).
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import type { AffiliateProgram, ProductAttribute, ProductDecision, ProductDetail } from '@/api/types'
import { MockBadge } from '@/components/MockBadge'
import { Button } from '@/components/ui/button'
import { Alert, Card, Input, Label } from '@/components/ui/form'
import { formatDateTime } from '@/i18n'

export interface ProductDetailViewProps {
  nicheId: string
  state: 'loading' | 'error' | 'ready'
  errorCode?: string
  product?: ProductDetail
  decisionError: string | null
  onDecision: (decision: Exclude<ProductDecision, 'CANDIDATE'>, reason: string) => void
  onWatch: (programId: string, enabled: boolean) => void
  onAcknowledge: (programId: string, version: number) => void
  onRetry: () => void
}

const CRITERIA = ['fit', 'affiliate', 'eligibility', 'quality', 'price_fit']
const DECISIONS: Exclude<ProductDecision, 'CANDIDATE'>[] = ['SELECTED', 'WATCH', 'REJECTED']

function show(value: unknown): string {
  if (value === null || value === undefined) return 'UNKNOWN'
  if (Array.isArray(value)) return value.map(show).join('; ')
  if (typeof value === 'object') {
    return Object.entries(value as Record<string, unknown>)
      .filter(([, v]) => v !== null && v !== undefined && !(Array.isArray(v) && v.length === 0))
      .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(', ') : String(v)}`)
      .join(', ')
  }
  return String(value)
}

function Chip({ status }: { status: string }) {
  const { t } = useTranslation()
  return (
    <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs" data-status={status}>
      {t(`discovery.verification.${status}`, status)}
    </span>
  )
}

function AttributeRow({ a }: { a: ProductAttribute }) {
  const { t } = useTranslation()
  return (
    <li className="text-sm" data-testid={`attr-${a.key}`}>
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium">{t(`products.attr.${a.key}`, a.key)}</span>
        <Chip status={a.status} />
        <span>{a.status === 'UNKNOWN' ? t('discovery.unknown') : show(a.value)}</span>
      </div>
      {a.values.length > 0 && (
        <ul className="mt-1 space-y-1 pl-4 text-xs text-slate-600">
          {a.values.map((v) => (
            <li key={v.evidence_id}>
              {show(v.value)} · <Chip status={v.status} /> ·{' '}
              {v.source_url && (
                <a href={v.source_url} target="_blank" rel="noreferrer noopener" className="underline">
                  {v.source_url}
                </a>
              )}
              {v.collected_at && ` · ${formatDateTime(v.collected_at)}`}
            </li>
          ))}
        </ul>
      )}
    </li>
  )
}

function ProgramCard({ p, props }: { p: AffiliateProgram; props: ProductDetailViewProps }) {
  const { t } = useTranslation()
  const pending = p.terms_versions.find((v) => v.acknowledged_at === null && v.changes.length > 0)
  return (
    <Card className="space-y-2" data-testid="program">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-semibold">{p.name}</span>
        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs" data-testid="program-status">
          {t(`products.status.${p.verification_status}`)}
        </span>
        {p.data_origin === 'MOCK' && <MockBadge />}
      </div>
      <p className="text-xs text-slate-600">
        {t('products.detail.operator')}: {p.operator_name ?? p.operator_domain ?? t('discovery.unknown')} ·{' '}
        {t('products.detail.terms')}:{' '}
        {p.terms_url ? (
          <a href={p.terms_url} target="_blank" rel="noreferrer noopener" className="underline">
            {p.terms_url}
          </a>
        ) : (
          t('discovery.unknown')
        )}
      </p>
      <ul className="space-y-2">
        {p.attributes.map((a) => (
          <AttributeRow key={a.key} a={a} />
        ))}
      </ul>
      {pending && (
        <Alert className="flex items-center justify-between gap-2" data-testid="terms-changed">
          <span>{t('products.detail.termsChanged', { v: pending.version })}</span>
          <Button size="sm" variant="outline" onClick={() => props.onAcknowledge(p.program_id, pending.version)}>
            {t('products.detail.acknowledge')}
          </Button>
        </Alert>
      )}
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={p.watch_enabled}
          onChange={(e) => props.onWatch(p.program_id, e.target.checked)}
          data-testid="watch"
        />
        {t('products.detail.watch')}
      </label>
      {p.last_checked_at && (
        <p className="text-xs text-slate-500">
          {t('products.detail.lastChecked')}: {formatDateTime(p.last_checked_at)}
          {p.last_check_error && ` · ${t('products.detail.checkError')}: ${p.last_check_error}`}
        </p>
      )}
    </Card>
  )
}

function DecisionCard({ p, props }: { p: ProductDetail; props: ProductDetailViewProps }) {
  const { t } = useTranslation()
  const [decision, setDecision] = useState<Exclude<ProductDecision, 'CANDIDATE'>>('WATCH')
  const [reason, setReason] = useState('')
  return (
    <Card className="space-y-2">
      <h2 className="text-lg font-semibold">{t('products.decision.title')}</h2>
      <p className="text-sm" data-testid="product-decision">
        {t(`products.decision.status.${p.decision_status}`)}
        {p.decision_reason && ` – ${p.decision_reason}`}
      </p>
      <p className="text-sm">
        {t('products.detail.aiRecommendation')}: {t(`products.recommendation.${p.ai_recommendation}`)}
        {p.ai_recommendation_reason && ` – ${p.ai_recommendation_reason}`}
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
          onChange={(e) => setDecision(e.target.value as Exclude<ProductDecision, 'CANDIDATE'>)}
          data-testid="product-decision-select"
        >
          {DECISIONS.map((d) => (
            <option key={d} value={d}>
              {t(`products.decision.status.${d}`)}
            </option>
          ))}
        </select>
        <div className="grow space-y-1">
          <Label htmlFor="product-reason">{t('products.decision.reason')}</Label>
          <Input id="product-reason" value={reason} onChange={(e) => setReason(e.target.value)} />
        </div>
        <Button size="sm" type="submit" disabled={!reason.trim()}>
          {t('products.decision.save')}
        </Button>
      </form>
      {props.decisionError && <Alert>{t(`errors.${props.decisionError}`, t('errors.generic'))}</Alert>}
    </Card>
  )
}

export function ProductDetailView(props: ProductDetailViewProps) {
  const { t } = useTranslation()
  if (props.state === 'loading') return <p className="text-sm text-slate-500">{t('app.loading')}</p>
  if (props.state === 'error' || !props.product) {
    return (
      <Alert className="flex items-center justify-between gap-4">
        <span>{t(`errors.${props.errorCode ?? 'generic'}`, t('errors.generic'))}</span>
        <Button size="sm" variant="outline" onClick={props.onRetry}>
          {t('app.retry')}
        </Button>
      </Alert>
    )
  }
  const p = props.product
  const ev = p.evaluation
  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-2xl font-semibold">{p.name}</h1>
          {p.data_origin === 'MOCK' && <MockBadge />}
          <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs" data-testid="readiness">
            {t(`products.readiness.${p.readiness_status}`)}
          </span>
          {p.risk_flags.map((f) => (
            <span key={f} className="rounded-full bg-amber-100 px-2 py-0.5 text-xs">
              {t(`products.flags.${f}`, f)}
            </span>
          ))}
        </div>
        <Link to={`/niches/${props.nicheId}/products`} className="text-sm underline">
          {t('products.title')}
        </Link>
        <Alert variant="info">{t(p.disclaimer_key)}</Alert>
        <p className="text-xs text-slate-500">{t('products.detail.noRegistration')}</p>
      </div>

      <Card className="space-y-2" data-testid="product-scoring">
        {!ev ? (
          <p className="text-sm text-slate-500">{t('discovery.unknown')}</p>
        ) : (
          <>
            <dl className="grid gap-2 text-sm sm:grid-cols-3">
              <div>
                <dt className="text-slate-500">{t('products.score.opportunity')}</dt>
                <dd>{ev.opportunity_score ?? t('products.score.insufficient')}</dd>
              </div>
              <div>
                <dt className="text-slate-500">{t('products.score.confidence')}</dt>
                <dd>{ev.confidence_score ?? t('discovery.unknown')}</dd>
              </div>
              <div>
                <dt className="text-slate-500">{t('products.score.coverage')}</dt>
                <dd>{ev.coverage == null ? t('discovery.unknown') : `${ev.coverage}%`}</dd>
              </div>
            </dl>
            <ul className="space-y-1 text-sm">
              {CRITERIA.map((k) => {
                const c = ev.criteria[k]
                return (
                  <li key={k} className="flex flex-wrap items-center gap-2">
                    <span className="font-medium">{t(`products.criteria.${k}`)}</span>
                    <span>{c?.level ?? t('discovery.unknown')}</span>
                    {c && <Chip status={c.status} />}
                  </li>
                )
              })}
            </ul>
            {ev.missing.length > 0 && (
              <p className="text-xs text-slate-500">
                {t('products.score.missing')}:{' '}
                {ev.missing.map((m) => t(`products.attr.${m}`, t(`products.criteria.${m}`, m))).join(', ')}
              </p>
            )}
            {ev.weights_version !== null && (
              <p className="text-xs text-slate-500">{t('products.score.weightsVersion', { v: ev.weights_version })}</p>
            )}
          </>
        )}
      </Card>

      <DecisionCard p={p} props={props} />

      <Card className="space-y-2">
        <h2 className="text-lg font-semibold">{t('products.detail.attributes')}</h2>
        <ul className="space-y-2">
          {p.attributes.map((a) => (
            <AttributeRow key={a.key} a={a} />
          ))}
        </ul>
      </Card>

      <Card className="space-y-2">
        <h2 className="text-lg font-semibold">{t('products.detail.painPoints')}</h2>
        <ul className="list-disc pl-5 text-sm">
          {p.pain_points.map((pp) => (
            <li key={pp.pain_point_id}>{pp.title}</li>
          ))}
        </ul>
      </Card>

      <div className="space-y-2">
        <h2 className="text-lg font-semibold">{t('products.detail.programs')}</h2>
        {p.programs.length === 0 ? (
          <p className="text-sm text-slate-500">{t('products.detail.noPrograms')}</p>
        ) : (
          p.programs.map((prog) => <ProgramCard key={prog.program_id} p={prog} props={props} />)
        )}
      </div>
    </div>
  )
}
