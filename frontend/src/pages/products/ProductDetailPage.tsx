// Container E2 màn hình 2 – Chi tiết sản phẩm (T054, T059).
import { useParams } from 'react-router'
import { ApiError } from '@/api/client'
import { useAcknowledgeTerms, useProduct, useProductDecision, useProgramWatch } from '@/api/products'
import { Layout } from '@/app/Layout'
import { ProductDetailView } from '@/pages/products/ProductDetailView'

function code(err: unknown): string | undefined {
  return err instanceof ApiError ? (err.code === 'NETWORK' ? 'network' : err.code) : err ? 'generic' : undefined
}

export function ProductDetailPage() {
  const { nicheId = '', productId = '' } = useParams()
  const product = useProduct(productId, nicheId)
  const decide = useProductDecision(productId, nicheId)
  const watch = useProgramWatch(productId, nicheId)
  const ack = useAcknowledgeTerms(productId, nicheId)
  return (
    <Layout syncProfile>
      <ProductDetailView
        nicheId={nicheId}
        state={product.isPending ? 'loading' : product.isError ? 'error' : 'ready'}
        errorCode={code(product.error)}
        product={product.data}
        decisionError={code(decide.error) ?? null}
        onDecision={(decision, reason) => decide.mutate({ decision, reason })}
        onWatch={(programId, enabled) => watch.mutate({ programId, enabled })}
        onAcknowledge={(programId, version) => ack.mutate({ programId, version })}
        onRetry={() => void product.refetch()}
      />
    </Layout>
  )
}
