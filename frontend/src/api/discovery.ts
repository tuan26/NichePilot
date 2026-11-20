// E1 – hook API lượt khám phá (T067). Điều khiển job dùng API job của E0 (/api/v1/jobs/{id}/pause|resume|cancel).
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/api/client'
import type { DiscoveryRun, DiscoveryRunCreate } from '@/api/types'

export type RunAction = 'pause' | 'resume' | 'cancel'

export function useDiscoveryRuns() {
  return useQuery({
    queryKey: ['discovery-runs'],
    queryFn: () => api<{ items: DiscoveryRun[] }>('/api/v1/discovery/runs').then((r) => r.items),
    refetchInterval: 10_000,
  })
}

export function useCreateRun() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: DiscoveryRunCreate) => api<DiscoveryRun>('/api/v1/discovery/runs', { method: 'POST', body }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['discovery-runs'] }),
  })
}

export function useRunAction() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ jobId, action }: { jobId: string; action: RunAction }) =>
      api(`/api/v1/jobs/${jobId}/${action}`, { method: 'POST' }),
    onSettled: () => qc.invalidateQueries({ queryKey: ['discovery-runs'] }),
  })
}
