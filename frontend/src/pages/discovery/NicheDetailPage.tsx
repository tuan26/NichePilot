// Container màn hình 3 – Chi tiết ngách (T084, FR-026, FR-013e).
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useParams } from 'react-router'
import { ApiError } from '@/api/client'
import { useEraseEvidence, useNiche, useRecordDecision, useResolveSimilarity } from '@/api/discovery'
import { Layout } from '@/app/Layout'
import { NicheDetailView } from '@/pages/discovery/NicheDetailView'

function code(err: unknown): string | undefined {
  return err instanceof ApiError ? (err.code === 'NETWORK' ? 'network' : err.code) : err ? 'generic' : undefined
}

export function NicheDetailPage() {
  const { t } = useTranslation()
  const { nicheId = '' } = useParams()
  const niche = useNiche(nicheId)
  const erase = useEraseEvidence(nicheId)
  const resolve = useResolveSimilarity(nicheId)
  const decide = useRecordDecision(nicheId)
  const [confirmId, setConfirmId] = useState<string | null>(null)
  return (
    <Layout
      syncProfile
      actions={
        <Link to="/discovery/runs" className="text-sm text-slate-600 underline">
          {t('nav.discovery')}
        </Link>
      }
    >
      <NicheDetailView
        state={niche.isPending ? 'loading' : niche.isError ? 'error' : 'ready'}
        errorCode={code(niche.error)}
        niche={niche.data}
        erasing={erase.isPending}
        eraseError={code(erase.error) ?? null}
        confirmEvidenceId={confirmId}
        onAskErase={setConfirmId}
        onCancelErase={() => setConfirmId(null)}
        onConfirmErase={(evidenceId, reason, scope) =>
          erase.mutate({ evidenceId, reason, scope }, { onSuccess: () => setConfirmId(null) })
        }
        onRetry={() => void niche.refetch()}
        onResolveDuplicate={(pair, status, keep) => resolve.mutate({ id: pair.id, status, keep })}
        onDecision={(decision, reason) => decide.mutate({ decision, reason })}
        decisionError={code(decide.error) ?? null}
      />
    </Layout>
  )
}
