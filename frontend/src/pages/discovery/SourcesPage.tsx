// Container màn hình quản lý nguồn (T110).
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import { ApiError } from '@/api/client'
import { useSources, useUpdateSource } from '@/api/discovery'
import { Layout } from '@/app/Layout'
import { SourcesView } from '@/pages/discovery/SourcesView'

function code(err: unknown): string | undefined {
  return err instanceof ApiError ? (err.code === 'NETWORK' ? 'network' : err.code) : err ? 'generic' : undefined
}

export function SourcesPage() {
  const { t } = useTranslation()
  const sources = useSources()
  const update = useUpdateSource()
  const [restart, setRestart] = useState(false)
  return (
    <Layout
      syncProfile
      actions={
        <Link to="/discovery/runs" className="text-sm text-slate-600 underline">
          {t('nav.discovery')}
        </Link>
      }
    >
      <SourcesView
        state={sources.isPending ? 'loading' : sources.isError ? 'error' : 'ready'}
        errorCode={code(sources.error)}
        sources={sources.data ?? []}
        saving={update.isPending}
        error={code(update.error) ?? null}
        restartNotice={restart}
        onUpdate={(id, body) =>
          update.mutate({ id, body }, { onSuccess: (s) => s.requires_service_restart && setRestart(true) })
        }
        onRetry={() => void sources.refetch()}
      />
    </Layout>
  )
}
