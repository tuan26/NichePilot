// E2 màn hình 1 – Sản phẩm theo ngách (T054, FR-032, FR-035, FR-036): 2 danh sách, điểm + Coverage + còn thiếu, trạng thái sẵn
// sàng affiliate, nhãn MOCK. View thuần; container ở NicheProductsPage. Chú thích "không phải dự báo doanh thu" luôn hiển thị.
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import type { ProductItem, ProductList } from '@/api/types'
import { MockBadge } from '@/components/MockBadge'
import { Button } from '@/components/ui/button'
import { Alert, Card } from '@/components/ui/form'

export interface NicheProductsViewProps {
  nicheId: string
  list: ProductList
  state: 'loading' | 'error' | 'ready'
  errorCode?: string
  items: ProductItem[]
  includeMock: boolean
  running: boolean
  runError: string | null
  runStarted: boolean
  onListChange: (list: ProductList) => void
  onIncludeMockChange: (v: boolean) => void
  onRun: () => void
  onRetry: () => void
}

const LISTS: ProductList[] = ['ranked', 'needs_research']

function ProductRow({ p, nicheId }: { p: ProductItem; nicheId: string }) {
  const { t } = useTranslation()
  const ev = p.evaluation
  return (
    <Card className="space-y-2" data-testid="product-row">
      <div className="flex flex-wrap items-center gap-2">
        <Link to={`/niches/${nicheId}/products/${p.product_id}`} className="font-semibold underline">
          {p.name}
        </Link>
        <span className="text-sm text-slate-600">{p.official_domain ?? t('discovery.unknown')}</span>
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
      <dl className="grid gap-2 text-sm sm:grid-cols-4">
        <div>
          <dt className="text-slate-500">{t('products.score.opportunity')}</dt>
          <dd data-testid="product-opportunity">
            {ev?.opportunity_score ?? t('products.score.insufficient')}
          </dd>
        </div>
        <div>
          <dt className="text-slate-500">{t('products.score.confidence')}</dt>
          <dd>{ev?.confidence_score ?? t('discovery.unknown')}</dd>
        </div>
        <div>
          <dt className="text-slate-500">{t('products.score.coverage')}</dt>
          <dd>{ev?.coverage == null ? t('discovery.unknown') : `${ev.coverage}%`}</dd>
        </div>
        <div>
          <dt className="text-slate-500">{t('products.decision.title')}</dt>
          <dd>{t(`products.decision.status.${p.decision_status}`)}</dd>
        </div>
      </dl>
      {ev && ev.missing.length > 0 && (
        <p className="text-xs text-slate-500">
          {t('products.score.missing')}: {ev.missing.map((m) => t(`products.attr.${m}`, t(`products.criteria.${m}`, m))).join(', ')}
        </p>
      )}
    </Card>
  )
}

export function NicheProductsView(props: NicheProductsViewProps) {
  const { t } = useTranslation()
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold">{t('products.title')}</h1>
          <Link to={`/niches/${props.nicheId}`} className="text-sm underline">
            {t('products.back')}
          </Link>
          <Button size="sm" className="ml-auto" disabled={props.running} onClick={props.onRun} data-testid="run-products">
            {t('products.run')}
          </Button>
        </div>
        <Alert variant="info">{t('products.opportunity.disclaimer')}</Alert>
        {props.runError && <Alert data-testid="run-error">{t(`errors.${props.runError}`, t('errors.generic'))}</Alert>}
        {props.runStarted && <Alert variant="info">{t('products.runStarted')}</Alert>}
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
            {t(`products.list.${l}`)}
          </Button>
        ))}
        <label className="ml-auto flex items-center gap-2 text-sm">
          <input type="checkbox" checked={props.includeMock} onChange={(e) => props.onIncludeMockChange(e.target.checked)} />
          {t('products.includeMock')}
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
      {props.state === 'ready' && props.items.length === 0 && <p className="text-sm text-slate-500">{t('products.empty')}</p>}
      {props.state === 'ready' && props.items.map((p) => <ProductRow key={p.product_id} p={p} nicheId={props.nicheId} />)}
    </div>
  )
}
