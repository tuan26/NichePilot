// E4 – trạng thái job và thao tác hợp lệ (khớp máy trạng thái/API E0).
import type { JobAction } from '@/api/dashboard'

export const JOB_STATUSES = ['QUEUED', 'RUNNING', 'RETRY_SCHEDULED', 'PAUSED', 'PAUSED_BUDGET', 'SUCCEEDED', 'FAILED', 'CANCELLED'] as const

/** Thao tác hợp lệ theo trạng thái (khớp API E0: pause chỉ RUNNING, resume PAUSED*, retry FAILED, cancel khi chưa kết thúc). */
export function allowedActions(status: string): JobAction[] {
  const out: JobAction[] = []
  if (status === 'RUNNING') out.push('pause')
  if (status === 'PAUSED' || status === 'PAUSED_BUDGET') out.push('resume')
  if (status === 'FAILED') out.push('retry')
  if (['QUEUED', 'RUNNING', 'RETRY_SCHEDULED', 'PAUSED', 'PAUSED_BUDGET'].includes(status)) out.push('cancel')
  return out
}
