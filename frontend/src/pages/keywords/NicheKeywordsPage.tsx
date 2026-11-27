// Container E3 màn hình 1 – Cluster keyword theo ngách (T036).
import { useState } from 'react'
import { useParams } from 'react-router'
import { ApiError } from '@/api/client'
import { useNicheClusters, useStartKeywordRun } from '@/api/keywords'
import type { KeywordList } from '@/api/types'
import { Layout } from '@/app/Layout'
import { NicheKeywordsView } from '@/pages/keywords/NicheKeywordsView'

function code(err: unknown): string | undefined {
  return err instanceof ApiError ? (err.code === 'NETWORK' ? 'network' : err.code) : err ? 'generic' : undefined
}

export function NicheKeywordsPage() {
  const { nicheId = '' } = useParams()
  const [list, setList] = useState<KeywordList>('ranked')
  const [includeMock, setIncludeMock] = useState(false)
  const clusters = useNicheClusters(nicheId, list, includeMock)
  const run = useStartKeywordRun(nicheId)
  return (
    <Layout syncProfile>
      <NicheKeywordsView
        nicheId={nicheId}
        list={list}
        state={clusters.isPending ? 'loading' : clusters.isError ? 'error' : 'ready'}
        errorCode={code(clusters.error)}
        items={clusters.data ?? []}
        includeMock={includeMock}
        running={run.isPending}
        runError={code(run.error) ?? null}
        runStarted={run.isSuccess}
        onListChange={setList}
        onIncludeMockChange={setIncludeMock}
        onRun={() => run.mutate()}
        onRetry={() => void clusters.refetch()}
      />
    </Layout>
  )
}
