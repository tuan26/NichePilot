// E4 Cài đặt (FR-017…FR-019; FR-055 E0; BR-10): sửa cấu hình KHÔNG bí mật; provider/model/profile chỉ đọc – không có thao tác xác minh
// model, sửa giá, kiểm tra kết nối hay bật gọi có phí. Ngôn ngữ giao diện độc lập với ngôn ngữ nội dung/nghiên cứu.
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import type { Budget, ModelProfile, Project, Provider, Setting } from '@/api/dashboard'
import { Button } from '@/components/ui/button'
import { Alert, Card, Input, Label } from '@/components/ui/form'
import { EDITABLE_SETTINGS } from '@/lib/settings'
import { LoadError, Loading, type LoadState } from '@/pages/dashboard/common'


export interface FieldError {
  field: string
  code: string
}

export interface SettingsViewProps {
  state: LoadState
  errorCode?: string
  settings: Setting[]
  project?: Project
  budget?: Budget
  providers: Provider[]
  profiles: ModelProfile[]
  paidCallsEnabled?: boolean
  saved: string | null
  error: { code: string; fields: FieldError[] } | null
  onSaveSettings: (items: { key: string; value: unknown; version: number }[]) => void
  onSaveProject: (body: Partial<Pick<Project, 'target_market' | 'research_language' | 'content_language'>>) => void
  onSaveBudget: (body: { daily_usd: string; monthly_usd: string; per_job_default_usd: string; warning_threshold: number }) => void
  onRetry: () => void
}

function FieldMsg({ field, error }: { field: string; error: SettingsViewProps['error'] }) {
  const { t } = useTranslation()
  const f = error?.fields.find((x) => x.field === field || x.field.endsWith(`.${field}`))
  return f ? (
    <p className="text-xs text-red-700" data-testid={`field-error-${field}`}>
      {t(`dashboard.settings.validation.${f.code}`, t('dashboard.settings.validation.invalid'))}
    </p>
  ) : null
}

function SettingsForm({ props }: { props: SettingsViewProps }) {
  const { t } = useTranslation()
  const byKey = Object.fromEntries(props.settings.map((s) => [s.key, s]))
  const [values, setValues] = useState<Record<string, string>>(() =>
    Object.fromEntries(EDITABLE_SETTINGS.map((k) => [k, byKey[k] === undefined ? '' : String(byKey[k].value)])),
  )
  return (
    <form
      className="space-y-2"
      onSubmit={(e) => {
        e.preventDefault()
        const items = EDITABLE_SETTINGS.filter((k) => byKey[k] && values[k] !== String(byKey[k].value)).map((k) => ({
          key: k,
          value: typeof byKey[k].value === 'number' ? Number(values[k]) : values[k],
          version: byKey[k].version,
        }))
        if (items.length) props.onSaveSettings(items)
      }}
    >
      {EDITABLE_SETTINGS.map((k) => (
        <div key={k} className="space-y-1">
          <Label htmlFor={`s-${k}`}>{t(`dashboard.settings.keys.${k.replace(/\./g, '_')}`)}</Label>
          {k === 'ui.default_locale' ? (
            <select
              id={`s-${k}`}
              className="block rounded-md border border-slate-300 px-2 py-1 text-sm"
              value={values[k]}
              onChange={(e) => setValues({ ...values, [k]: e.target.value })}
            >
              <option value="vi">{t('language.vi')}</option>
              <option value="en">{t('language.en')}</option>
            </select>
          ) : (
            <Input id={`s-${k}`} value={values[k]} onChange={(e) => setValues({ ...values, [k]: e.target.value })} />
          )}
          <FieldMsg field={k} error={props.error} />
        </div>
      ))}
      <Button size="sm" type="submit" data-testid="save-settings">
        {t('dashboard.settings.save')}
      </Button>
    </form>
  )
}

function ProjectForm({ props }: { props: SettingsViewProps }) {
  const { t } = useTranslation()
  const p = props.project
  const [v, setV] = useState({
    target_market: p?.target_market ?? '',
    content_language: p?.content_language ?? '',
    research_language: p?.research_language ?? '',
  })
  return (
    <form
      className="space-y-2"
      onSubmit={(e) => {
        e.preventDefault()
        props.onSaveProject(v)
      }}
    >
      {(['target_market', 'content_language', 'research_language'] as const).map((k) => (
        <div key={k} className="space-y-1">
          <Label htmlFor={`p-${k}`}>{t(`dashboard.settings.project.${k}`)}</Label>
          <Input id={`p-${k}`} value={v[k]} onChange={(e) => setV({ ...v, [k]: e.target.value })} />
          <FieldMsg field={k} error={props.error} />
        </div>
      ))}
      <p className="text-xs text-slate-500">{t('dashboard.settings.languageIndependent')}</p>
      <Button size="sm" type="submit" data-testid="save-project">
        {t('dashboard.settings.save')}
      </Button>
    </form>
  )
}

function BudgetForm({ props }: { props: SettingsViewProps }) {
  const { t } = useTranslation()
  const l = props.budget?.limits
  const [v, setV] = useState({
    daily_usd: l?.daily_usd ?? '',
    monthly_usd: l?.monthly_usd ?? '',
    per_job_default_usd: l?.per_job_default_usd ?? '',
    warning_threshold: String(l?.warning_threshold ?? '0.8'),
  })
  return (
    <form
      className="space-y-2"
      onSubmit={(e) => {
        e.preventDefault()
        props.onSaveBudget({ ...v, warning_threshold: Number(v.warning_threshold) })
      }}
    >
      {(['daily_usd', 'monthly_usd', 'per_job_default_usd', 'warning_threshold'] as const).map((k) => (
        <div key={k} className="space-y-1">
          <Label htmlFor={`b-${k}`}>{t(`dashboard.settings.budget.${k}`)}</Label>
          <Input id={`b-${k}`} value={v[k]} onChange={(e) => setV({ ...v, [k]: e.target.value })} />
          <FieldMsg field={k} error={props.error} />
        </div>
      ))}
      <Button size="sm" type="submit" data-testid="save-budget">
        {t('dashboard.settings.save')}
      </Button>
    </form>
  )
}

export function SettingsView(props: SettingsViewProps) {
  const { t } = useTranslation()
  if (props.state === 'loading') return <Loading />
  if (props.state === 'error') return <LoadError code={props.errorCode} onRetry={props.onRetry} />
  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-semibold">{t('dashboard.settings.title')}</h1>
      {props.saved && <Alert variant="info">{t('dashboard.settings.saved')}</Alert>}
      {props.error && <Alert data-testid="settings-error">{t(`errors.${props.error.code}`, t('errors.generic'))}</Alert>}
      <div className="grid gap-4 md:grid-cols-2">
        <Card className="space-y-2">
          <h2 className="text-lg font-semibold">{t('dashboard.settings.general')}</h2>
          <SettingsForm props={props} />
        </Card>
        <Card className="space-y-2">
          <h2 className="text-lg font-semibold">{t('dashboard.settings.projectTitle')}</h2>
          {props.project ? <ProjectForm props={props} /> : <Loading />}
        </Card>
        <Card className="space-y-2">
          <h2 className="text-lg font-semibold">{t('dashboard.settings.budgetTitle')}</h2>
          {props.budget ? <BudgetForm props={props} /> : <Loading />}
        </Card>
        <Card className="space-y-2" data-testid="ai-readonly">
          <h2 className="text-lg font-semibold">{t('dashboard.settings.aiTitle')}</h2>
          <p className="text-sm" data-testid="paid-calls-state">
            {t('dashboard.settings.paidCalls')}: {props.paidCallsEnabled ? t('status.on') : t('status.off')}
          </p>
          <ul className="text-sm">
            {props.providers.map((p) => (
              <li key={p.provider}>
                {p.provider}: {p.configured ? `${t('status.configured')} ${p.key_hint ?? ''}` : t('status.notConfigured')}
              </li>
            ))}
          </ul>
          <table className="w-full text-left text-xs">
            <thead className="text-slate-500">
              <tr>
                <th>{t('dashboard.settings.taskType')}</th>
                <th>{t('dashboard.costs.provider')}</th>
                <th>{t('dashboard.costs.model')}</th>
              </tr>
            </thead>
            <tbody>
              {props.profiles.map((m) => (
                <tr key={m.task_type} className="border-t border-slate-200">
                  <td>{m.task_type}</td>
                  <td>{m.provider}</td>
                  <td>{m.model}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="text-xs text-slate-500">{t('dashboard.settings.readOnlyNote')}</p>
        </Card>
      </div>
    </div>
  )
}
