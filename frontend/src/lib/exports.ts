// E4 FR-020 – dựng bảng CSV cho 3 danh sách (xếp hạng ngách E1, sản phẩm theo ngách E2, keyword theo cluster E3). Tiêu đề theo ngôn
// ngữ giao diện; giá trị thiếu → UNKNOWN; có cột data_origin để phân biệt MOCK.
import type { TFunction } from 'i18next'
import type { KeywordItem, NicheSummary, ProductItem } from '@/api/types'
import { type CsvCell, toCsv } from '@/lib/csv'

export function rankingCsv(items: NicheSummary[], t: TFunction): string {
  const h = ['name', 'country', 'opportunity', 'confidence', 'coverage', 'evidence', 'decision', 'data_origin'].map((k) =>
    t(`dashboard.csv.${k}`),
  )
  const rows: CsvCell[][] = items.map((n) => [
    n.name,
    n.country,
    n.opportunity_score,
    n.confidence_score,
    n.coverage,
    n.evidence_status,
    n.decision_status,
    n.data_origin,
  ])
  return toCsv(h, rows)
}

export function productsCsv(items: ProductItem[], t: TFunction): string {
  const h = ['name', 'domain', 'readiness', 'opportunity', 'confidence', 'coverage', 'decision', 'data_origin'].map((k) =>
    t(`dashboard.csv.${k}`),
  )
  const rows: CsvCell[][] = items.map((p) => [
    p.name,
    p.official_domain,
    p.readiness_status,
    p.evaluation?.opportunity_score,
    p.evaluation?.confidence_score,
    p.evaluation?.coverage,
    p.decision_status,
    p.data_origin,
  ])
  return toCsv(h, rows)
}

export function keywordsCsv(items: KeywordItem[], t: TFunction): string {
  const h = ['keyword', 'intent', 'length', 'volume', 'cpc', 'kd', 'opportunity', 'confidence', 'data_origin'].map((k) =>
    t(`dashboard.csv.${k}`),
  )
  const rows: CsvCell[][] = items.map((k) => [
    k.text,
    k.intent,
    k.length_class,
    k.metrics.search_volume.source ? k.metrics.search_volume.value : null,
    k.metrics.cpc.source ? k.metrics.cpc.value : null,
    k.metrics.keyword_difficulty.source ? k.metrics.keyword_difficulty.value : null,
    k.evaluation?.opportunity_score,
    k.evaluation?.confidence_score,
    k.data_origin,
  ])
  return toCsv(h, rows)
}
