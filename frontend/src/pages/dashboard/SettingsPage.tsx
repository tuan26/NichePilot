// Container E4 – Cài đặt.
import { useQuery } from '@tanstack/react-query'
import { api, ApiError, errorCode } from '@/api/client'
import { useBudget, useModelProfiles, useProject, useProviders, useSaveBudget, useSaveProject, useSaveSettings, useSettings } from '@/api/dashboard'
import { Layout } from '@/app/Layout'
import { SettingsView } from '@/pages/dashboard/SettingsView'

function toError(err: unknown) {
  if (!err) return null
  return { code: errorCode(err) ?? 'generic', fields: err instanceof ApiError ? err.errors : [] }
}

export function SettingsPage() {
  const settings = useSettings()
  const project = useProject()
  const budget = useBudget()
  const providers = useProviders()
  const profiles = useModelProfiles()
  const status = useQuery({ queryKey: ['system-status'], queryFn: () => api<{ paid_calls_enabled: boolean }>('/api/v1/system/status') })
  const saveSettings = useSaveSettings()
  const saveProject = useSaveProject()
  const saveBudget = useSaveBudget()
  const lastError = saveSettings.error ?? saveProject.error ?? saveBudget.error
  const saved = saveSettings.isSuccess || saveProject.isSuccess || saveBudget.isSuccess ? 'ok' : null
  return (
    <Layout syncProfile>
      <SettingsView
        state={settings.isPending ? 'loading' : settings.isError ? 'error' : 'ready'}
        errorCode={errorCode(settings.error)}
        settings={settings.data ?? []}
        project={project.data}
        budget={budget.data}
        providers={providers.data ?? []}
        profiles={profiles.data ?? []}
        paidCallsEnabled={status.data?.paid_calls_enabled}
        saved={lastError ? null : saved}
        error={toError(lastError)}
        onSaveSettings={(items) => saveSettings.mutate(items)}
        onSaveProject={(body) => saveProject.mutate(body)}
        onSaveBudget={(body) => saveBudget.mutate(body)}
        onRetry={() => void settings.refetch()}
      />
    </Layout>
  )
}
