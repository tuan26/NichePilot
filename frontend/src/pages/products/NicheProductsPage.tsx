// Container E2 màn hình 1 – Sản phẩm theo ngách (T054).
import { useState } from 'react'
import { useParams } from 'react-router'
import { ApiError } from '@/api/client'
import { useNicheProducts, useStartProductRun } from '@/api/products'
import type { ProductList } from '@/api/types'
import { Layout } from '@/app/Layout'
import { NicheProductsView } from '@/pages/products/NicheProductsView'

function code(err: unknown): string | undefined {
  return err instanceof ApiError ? (err.code === 'NETWORK' ? 'network' : err.code) : err ? 'generic' : undefined
}

export function NicheProductsPage() {
  const { nicheId = '' } = useParams()
  const [list, setList] = useState<ProductList>('ranked')
  const [includeMock, setIncludeMock] = useState(false)
  const products = useNicheProducts(nicheId, list, includeMock)
  const run = useStartProductRun(nicheId)
  return (
    <Layout syncProfile>
      <NicheProductsView
        nicheId={nicheId}
        list={list}
        state={products.isPending ? 'loading' : products.isError ? 'error' : 'ready'}
        errorCode={code(products.error)}
        items={products.data ?? []}
        includeMock={includeMock}
        running={run.isPending}
        runError={code(run.error) ?? null}
        runStarted={run.isSuccess}
        onListChange={setList}
        onIncludeMockChange={setIncludeMock}
        onRun={() => run.mutate()}
        onRetry={() => void products.refetch()}
      />
    </Layout>
  )
}
