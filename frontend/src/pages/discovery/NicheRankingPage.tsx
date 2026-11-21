// Container màn hình 2 – Bảng xếp hạng ngách (T099).
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link } from 'react-router'
import { ApiError } from '@/api/client'
import { useNiches } from '@/api/discovery'
import type { RankingList } from '@/api/types'
import { Layout } from '@/app/Layout'
import { NicheRankingView } from '@/pages/discovery/NicheRankingView'

function code(err: unknown): string | undefined {
  return err instanceof ApiError ? (err.code === 'NETWORK' ? 'network' : err.code) : err ? 'generic' : undefined
}

export function NicheRankingPage() {
  const { t } = useTranslation()
  const [list, setList] = useState<RankingList>('research')
  const [includeMock, setIncludeMock] = useState(false)
  const niches = useNiches(list, includeMock)
  return (
    <Layout
      syncProfile
      actions={
        <Link to="/discovery/runs" className="text-sm text-slate-600 underline">
          {t('nav.discovery')}
        </Link>
      }
    >
      <NicheRankingView
        list={list}
        state={niches.isPending ? 'loading' : niches.isError ? 'error' : 'ready'}
        errorCode={code(niches.error)}
        items={niches.data ?? []}
        includeMock={includeMock}
        onListChange={setList}
        onIncludeMockChange={setIncludeMock}
        onRetry={() => void niches.refetch()}
      />
    </Layout>
  )
}
