// Container E4 – chi tiết job.
import { errorCode } from '@/api/client'
import { useParams } from 'react-router'
import { useJob, useJobAction, useJobSteps } from '@/api/dashboard'
import { Layout } from '@/app/Layout'
import { JobDetailView } from '@/pages/dashboard/JobDetailView'

export function JobDetailPage() {
  const { jobId = '' } = useParams()
  const job = useJob(jobId)
  const steps = useJobSteps(jobId)
  const action = useJobAction()
  return (
    <Layout syncProfile>
      <JobDetailView
        state={job.isPending ? 'loading' : job.isError ? 'error' : 'ready'}
        errorCode={errorCode(job.error)}
        job={job.data}
        steps={steps.data ?? []}
        actionError={errorCode(action.error) ?? null}
        onAction={(id, a) => action.mutate({ jobId: id, action: a })}
        onRetry={() => void job.refetch()}
      />
    </Layout>
  )
}
