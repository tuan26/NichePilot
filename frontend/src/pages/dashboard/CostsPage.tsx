// Container E4 – Chi phí.
import { errorCode } from '@/api/client'
import { useState } from 'react'
import { useBudget, useCostSummary } from '@/api/dashboard'
import { Layout } from '@/app/Layout'
import { CostsView } from '@/pages/dashboard/CostsView'

export function CostsPage() {
  const [period, setPeriod] = useState<'day' | 'month'>('month')
  const budget = useBudget()
  const real = useCostSummary(period, 'REAL')
  const mock = useCostSummary(period, 'MOCK')
  return (
    <Layout syncProfile>
      <CostsView
        state={budget.isPending ? 'loading' : budget.isError ? 'error' : 'ready'}
        errorCode={errorCode(budget.error)}
        budget={budget.data}
        real={real.data}
        mock={mock.data}
        period={period}
        onPeriodChange={setPeriod}
        onRetry={() => void budget.refetch()}
      />
    </Layout>
  )
}
