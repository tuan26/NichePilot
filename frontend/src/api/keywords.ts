// E3 – hook API keyword & audience (T036). Lượt nghiên cứu keyword là job E0 `keywords.run`.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/api/client'
import type { ClusterDecision, ClusterDetail, ClusterItem, KeywordList, KeywordSummary } from '@/api/types'

const mock = (v: boolean) => (v ? 'true' : 'false')

export function useNicheClusters(nicheId: string, list: KeywordList, includeMock: boolean) {
  return useQuery({
    queryKey: ['keyword-clusters', nicheId, list, includeMock],
    queryFn: () =>
      api<{ items: ClusterItem[] }>(`/api/v1/niches/${nicheId}/keyword-clusters?list=${list}&include_mock=${mock(includeMock)}`).then(
        (r) => r.items,
      ),
  })
}

export function useKeywordSummary(nicheId: string, includeMock: boolean) {
  return useQuery({
    queryKey: ['keyword-summary', nicheId, includeMock],
    queryFn: () => api<KeywordSummary>(`/api/v1/niches/${nicheId}/keyword-summary?include_mock=${mock(includeMock)}`),
  })
}

export function useStartKeywordRun(nicheId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => api<{ job_id: string; run_id: string }>('/api/v1/keyword-runs', { method: 'POST', body: { niche_id: nicheId } }),
    onSettled: () => qc.invalidateQueries({ queryKey: ['keyword-clusters', nicheId] }),
  })
}

export function useCluster(clusterId: string) {
  return useQuery({
    queryKey: ['keyword-cluster', clusterId],
    queryFn: () => api<ClusterDetail>(`/api/v1/keyword-clusters/${clusterId}`),
  })
}

export function useClusterDecision(clusterId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ decision, reason }: { decision: Exclude<ClusterDecision, 'CANDIDATE'>; reason: string }) =>
      api<ClusterDetail>(`/api/v1/keyword-clusters/${clusterId}/decision`, { method: 'POST', body: { decision, reason } }),
    onSuccess: (data) => qc.setQueryData(['keyword-cluster', clusterId], data),
  })
}

export function useClusterWatch(clusterId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (enabled: boolean) =>
      api<ClusterDetail>(`/api/v1/keyword-clusters/${clusterId}/watch`, { method: 'PUT', body: { enabled } }),
    onSuccess: (data) => qc.setQueryData(['keyword-cluster', clusterId], data),
  })
}

export function useAcknowledgeSerp(clusterId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (version: number) =>
      api<ClusterDetail>(`/api/v1/keyword-clusters/${clusterId}/serp-versions/${version}/acknowledge`, { method: 'POST' }),
    onSuccess: (data) => qc.setQueryData(['keyword-cluster', clusterId], data),
  })
}
