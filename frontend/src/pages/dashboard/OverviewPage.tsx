// Container E4 – Tổng quan.
import { errorCode } from '@/api/client'
import { useState } from 'react'
import { useBudget, useOverview } from '@/api/dashboard'
import { Layout } from '@/app/Layout'
import { OverviewView } from '@/pages/dashboard/OverviewView'

export function OverviewPage() {
  const [includeMock, setIncludeMock] = useState(false)
  const overview = useOverview(includeMock)
  const budget = useBudget()
  return (
    <Layout syncProfile>
      <OverviewView
        state={overview.isPending ? 'loading' : overview.isError ? 'error' : 'ready'}
        errorCode={errorCode(overview.error)}
        data={overview.data}
        budget={budget.data}
        includeMock={includeMock}
        onIncludeMockChange={setIncludeMock}
        onRetry={() => void overview.refetch()}
      />
    </Layout>
  )
}
