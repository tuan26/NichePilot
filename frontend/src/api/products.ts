// E2 – hook API sản phẩm & chương trình affiliate (T053). Lượt tìm sản phẩm là job E0 `products.run`.
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '@/api/client'
import type { AffiliateProgram, ProductDecision, ProductDetail, ProductItem, ProductList, ProductSummary } from '@/api/types'

export function useNicheProducts(nicheId: string, list: ProductList, includeMock: boolean) {
  return useQuery({
    queryKey: ['niche-products', nicheId, list, includeMock],
    queryFn: () =>
      api<{ items: ProductItem[] }>(
        `/api/v1/niches/${nicheId}/products?list=${list}&include_mock=${includeMock ? 'true' : 'false'}`,
      ).then((r) => r.items),
  })
}

export function useProductSummary(nicheId: string, includeMock: boolean) {
  return useQuery({
    queryKey: ['product-summary', nicheId, includeMock],
    queryFn: () =>
      api<ProductSummary>(`/api/v1/niches/${nicheId}/product-summary?include_mock=${includeMock ? 'true' : 'false'}`),
  })
}

export function useStartProductRun(nicheId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => api<{ job_id: string; run_id: string }>('/api/v1/product-runs', { method: 'POST', body: { niche_id: nicheId } }),
    onSettled: () => qc.invalidateQueries({ queryKey: ['niche-products', nicheId] }),
  })
}

export function useProduct(productId: string, nicheId: string) {
  return useQuery({
    queryKey: ['product', productId, nicheId],
    queryFn: () => api<ProductDetail>(`/api/v1/products/${productId}?niche_id=${nicheId}`),
  })
}

export function useProductDecision(productId: string, nicheId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ decision, reason }: { decision: Exclude<ProductDecision, 'CANDIDATE'>; reason: string }) =>
      api<ProductDetail>(`/api/v1/products/${productId}/decision`, {
        method: 'POST',
        body: { niche_id: nicheId, decision, reason },
      }),
    onSuccess: (data) => qc.setQueryData(['product', productId, nicheId], data),
  })
}

export function useProgramWatch(productId: string, nicheId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ programId, enabled }: { programId: string; enabled: boolean }) =>
      api<AffiliateProgram>(`/api/v1/affiliate-programs/${programId}/watch`, { method: 'PUT', body: { enabled } }),
    onSettled: () => qc.invalidateQueries({ queryKey: ['product', productId, nicheId] }),
  })
}

export function useAcknowledgeTerms(productId: string, nicheId: string) {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ programId, version }: { programId: string; version: number }) =>
      api<AffiliateProgram>(`/api/v1/affiliate-programs/${programId}/terms-versions/${version}/acknowledge`, {
        method: 'POST',
      }),
    onSettled: () => qc.invalidateQueries({ queryKey: ['product', productId, nicheId] }),
  })
}
