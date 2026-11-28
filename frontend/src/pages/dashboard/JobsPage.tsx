// Container E4 – Agent Jobs.
import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'
import { api, errorCode } from '@/api/client'
import { useJobAction, useJobs, useScheduleDelete, useSchedules, useScheduleToggle } from '@/api/dashboard'
import { Layout } from '@/app/Layout'
import { JobsView } from '@/pages/dashboard/JobsView'

export function JobsPage() {
  const [status, setStatus] = useState('')
  const [jobType, setJobType] = useState('')
  const jobs = useJobs(status, jobType)
  const types = useQuery({ queryKey: ['job-types'], queryFn: () => api<{ job_type: string }[]>('/api/v1/job-types') })
  const schedules = useSchedules()
  const action = useJobAction()
  const toggle = useScheduleToggle()
  const del = useScheduleDelete()
  return (
    <Layout syncProfile>
      <JobsView
        state={jobs.isPending ? 'loading' : jobs.isError ? 'error' : 'ready'}
        errorCode={errorCode(jobs.error)}
        jobs={jobs.data?.items ?? []}
        total={jobs.data?.total ?? 0}
        status={status}
        jobType={jobType}
        jobTypes={(types.data ?? []).map((x) => x.job_type)}
        schedules={schedules.data ?? []}
        actionError={errorCode(action.error ?? toggle.error ?? del.error) ?? null}
        onStatusChange={setStatus}
        onJobTypeChange={setJobType}
        onAction={(jobId, a) => action.mutate({ jobId, action: a })}
        onToggleSchedule={(id, enabled) => toggle.mutate({ id, enabled })}
        onDeleteSchedule={(id) => del.mutate(id)}
        onRetry={() => void jobs.refetch()}
      />
    </Layout>
  )
}
