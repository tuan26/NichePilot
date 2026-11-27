// Container E3 màn hình 2 – Chi tiết cluster keyword (T036).
import { useParams } from 'react-router'
import { ApiError } from '@/api/client'
import { useAcknowledgeSerp, useCluster, useClusterDecision, useClusterWatch } from '@/api/keywords'
import { Layout } from '@/app/Layout'
import { KeywordClusterView } from '@/pages/keywords/KeywordClusterView'

function code(err: unknown): string | undefined {
  return err instanceof ApiError ? (err.code === 'NETWORK' ? 'network' : err.code) : err ? 'generic' : undefined
}

export function KeywordClusterPage() {
  const { nicheId = '', clusterId = '' } = useParams()
  const cluster = useCluster(clusterId)
  const decide = useClusterDecision(clusterId)
  const watch = useClusterWatch(clusterId)
  const ack = useAcknowledgeSerp(clusterId)
  return (
    <Layout syncProfile>
      <KeywordClusterView
        nicheId={nicheId}
        state={cluster.isPending ? 'loading' : cluster.isError ? 'error' : 'ready'}
        errorCode={code(cluster.error)}
        cluster={cluster.data}
        decisionError={code(decide.error) ?? null}
        onDecision={(decision, reason) => decide.mutate({ decision, reason })}
        onWatch={(enabled) => watch.mutate(enabled)}
        onAcknowledge={(version) => ack.mutate(version)}
        onRetry={() => void cluster.refetch()}
      />
    </Layout>
  )
}
