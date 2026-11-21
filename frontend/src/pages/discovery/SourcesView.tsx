// Quản lý nguồn dữ liệu (T110, FR-006c, FR-006d, FR-026). Chỉ nguồn ALLOWED mới có nút bật; không có tùy chọn bỏ qua cảnh báo hay
// dùng nguồn chưa xác minh (quyết định A1). Xác minh cần đủ mục theo source-verification.md §2.
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { SourcePolicy, SourceUpdate } from '@/api/types'
import { Button } from '@/components/ui/button'
import { Alert, Card, Input, Label } from '@/components/ui/form'

export interface SourcesViewProps {
  state: 'loading' | 'error' | 'ready'
  errorCode?: string
  sources: SourcePolicy[]
  saving: boolean
  error: string | null
  restartNotice: boolean
  onUpdate: (id: string, body: SourceUpdate) => void
  onRetry: () => void
}

const STATUSES = ['UNVERIFIED', 'ALLOWED', 'PROHIBITED'] as const

function VerifyForm({ s, props }: { s: SourcePolicy; props: SourcesViewProps }) {
  const { t } = useTranslation()
  const [open, setOpen] = useState(false)
  const [status, setStatus] = useState<'ALLOWED' | 'PROHIBITED' | 'UNVERIFIED'>(s.compliance_status)
  const [verifiedAt, setVerifiedAt] = useState(s.verified_at ?? '')
  const [note, setNote] = useState(s.verification_note ?? '')
  const [scope, setScope] = useState(s.permitted_use_scope ?? '')
  if (!open) {
    return (
      <Button size="sm" variant="outline" data-testid={`verify-${s.id}`} onClick={() => setOpen(true)}>
        {t('discovery.sources.verify')}
      </Button>
    )
  }
  const method = s.adapter_type === 'searxng_engine' ? 'SEARXNG_ENGINE' : s.adapter_type === 'http_json_api' ? 'OFFICIAL_API' : 'DATASET_DOWNLOAD'
  return (
    <form
      className="mt-2 grid gap-2 rounded-md border border-slate-200 p-3 text-sm"
      onSubmit={(e) => {
        e.preventDefault()
        props.onUpdate(s.id, {
          compliance_status: status,
          verified_at: verifiedAt || undefined,
          verification_note: note || undefined,
          allowed_access_methods: status === 'ALLOWED' ? [method] : undefined,
          permitted_use_scope: scope || undefined,
        })
      }}
    >
      <Label htmlFor={`st-${s.id}`}>{t('discovery.sources.status')}</Label>
      <select id={`st-${s.id}`} value={status} onChange={(e) => setStatus(e.target.value as typeof status)}>
        {STATUSES.map((v) => (
          <option key={v} value={v}>
            {v}
          </option>
        ))}
      </select>
      <Label htmlFor={`va-${s.id}`}>{t('discovery.sources.verifiedAt')}</Label>
      <Input id={`va-${s.id}`} type="date" value={verifiedAt} onChange={(e) => setVerifiedAt(e.target.value)} />
      <Label htmlFor={`vn-${s.id}`}>{t('discovery.sources.note')}</Label>
      <Input id={`vn-${s.id}`} value={note} maxLength={2000} onChange={(e) => setNote(e.target.value)} />
      <Label htmlFor={`sc-${s.id}`}>{t('discovery.sources.scope')}</Label>
      <Input id={`sc-${s.id}`} value={scope} maxLength={1000} onChange={(e) => setScope(e.target.value)} />
      <p className="text-xs text-slate-500">{t('discovery.sources.verifyHint')}</p>
      <Button size="sm" type="submit" disabled={props.saving}>
        {t('discovery.sources.save')}
      </Button>
    </form>
  )
}

export function SourcesView(props: SourcesViewProps) {
  const { t } = useTranslation()
  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-2xl font-semibold">{t('discovery.sources.title')}</h1>
        <p className="mt-1 text-sm text-slate-600">{t('discovery.sources.description')}</p>
      </div>
      {props.restartNotice && <Alert variant="warning">{t('discovery.sources.restart')}</Alert>}
      {props.error && <Alert>{t(`errors.${props.error}`, t('errors.generic'))}</Alert>}
      {props.state === 'loading' && <p className="text-sm text-slate-500">{t('app.loading')}</p>}
      {props.state === 'error' && (
        <Alert className="flex items-center justify-between gap-4">
          <span>{t(`errors.${props.errorCode ?? 'generic'}`, t('errors.generic'))}</span>
          <Button size="sm" variant="outline" onClick={props.onRetry}>
            {t('app.retry')}
          </Button>
        </Alert>
      )}
      {props.state === 'ready' && props.sources.length === 0 && (
        <p className="text-sm text-slate-500">{t('discovery.sources.empty')}</p>
      )}
      {props.state === 'ready' &&
        props.sources.map((s) => (
          <Card key={s.id} className="space-y-2" data-testid="source-row">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-semibold">{s.display_name}</span>
              <span className="text-xs text-slate-500">{s.source_key}</span>
              <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs">{s.compliance_status}</span>
              <span className="text-xs">{s.enabled ? t('discovery.sources.enabled') : t('discovery.sources.disabled')}</span>
            </div>
            <p className="text-xs text-slate-500">
              <a href={s.tos_url} target="_blank" rel="noreferrer noopener" className="underline">
                {t('discovery.sources.tos')}
              </a>
              {s.verified_at && ` · ${t('discovery.sources.verifiedOn', { date: s.verified_at })}`}
            </p>
            <div className="flex flex-wrap gap-2">
              {s.compliance_status === 'ALLOWED' && (
                <Button
                  size="sm"
                  data-testid={`enable-${s.id}`}
                  disabled={props.saving}
                  onClick={() => props.onUpdate(s.id, { enabled: !s.enabled })}
                >
                  {s.enabled ? t('discovery.sources.disable') : t('discovery.sources.enable')}
                </Button>
              )}
              <VerifyForm s={s} props={props} />
            </div>
          </Card>
        ))}
    </div>
  )
}
