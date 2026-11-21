// Container màn hình 1 – Lượt khám phá (T068, FR-026, FR-027, FR-032).
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import { ApiError } from '@/api/client'
import { useCreateRun, useDiscoveryRuns, useRunAction } from '@/api/discovery'
import { Layout } from '@/app/Layout'
import { DiscoveryRunsView } from '@/pages/discovery/DiscoveryRunsView'

function code(err: unknown): string | undefined {
  return err instanceof ApiError ? (err.code === 'NETWORK' ? 'network' : err.code) : err ? 'generic' : undefined
}

export function DiscoveryRunsPage() {
  const { t } = useTranslation()
  const runs = useDiscoveryRuns()
  const create = useCreateRun()
  const action = useRunAction()
  return (
    <Layout
      syncProfile
      actions={
        <span className="flex gap-3">
          <Link to="/niches" className="text-sm text-slate-600 underline">
            {t('nav.ranking')}
          </Link>
          <Link to="/sources" className="text-sm text-slate-600 underline">
            {t('nav.sources')}
          </Link>
          <Link to="/" className="text-sm text-slate-600 underline">
            {t('nav.status')}
          </Link>
        </span>
      }
    >
      <DiscoveryRunsView
        state={runs.isPending ? 'loading' : runs.isError ? 'error' : 'ready'}
        errorCode={code(runs.error)}
        runs={runs.data ?? []}
        creating={create.isPending}
        createError={code(create.error) ?? null}
        onCreate={(body) => create.mutate(body)}
        onAction={(jobId, a) => action.mutate({ jobId, action: a })}
        onRetry={() => void runs.refetch()}
      />
    </Layout>
  )
}
