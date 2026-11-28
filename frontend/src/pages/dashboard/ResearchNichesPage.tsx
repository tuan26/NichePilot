// Container E4 – trang Sản phẩm / Keyword toàn cục.
import { errorCode } from '@/api/client'
import { useState } from 'react'
import { useResearchNiches } from '@/api/dashboard'
import { Layout } from '@/app/Layout'
import { ResearchNichesView } from '@/pages/dashboard/ResearchNichesView'

export function ResearchNichesPage({ mode }: { mode: 'products' | 'keywords' }) {
  const [includeMock, setIncludeMock] = useState(false)
  const q = useResearchNiches(includeMock)
  return (
    <Layout syncProfile>
      <ResearchNichesView
        mode={mode}
        state={q.isPending ? 'loading' : q.isError ? 'error' : 'ready'}
        errorCode={errorCode(q.error)}
        items={q.data?.items ?? []}
        includeMock={includeMock}
        onIncludeMockChange={setIncludeMock}
        onRetry={() => void q.refetch()}
      />
    </Layout>
  )
}
