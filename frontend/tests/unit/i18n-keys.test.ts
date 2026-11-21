// T046 – Bản dịch VI/EN đầy đủ, không chuỗi UI hard-code (FR-060, SC-010)
import { readFileSync, readdirSync, statSync } from 'node:fs'
import { join } from 'node:path'
import { parseSync } from 'oxc-parser'
import { describe, expect, it } from 'vitest'
import errorCodes from '../../src/api/error-codes.json'
import en from '../../src/i18n/locales/en.json'
import vi from '../../src/i18n/locales/vi.json'

type Tree = { [key: string]: string | Tree }

function flatten(tree: Tree, prefix = ''): Record<string, string> {
  const out: Record<string, string> = {}
  for (const [k, v] of Object.entries(tree)) {
    const key = prefix ? `${prefix}.${k}` : k
    if (typeof v === 'string') out[key] = v
    else Object.assign(out, flatten(v, key))
  }
  return out
}

function walk(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const p = join(dir, name)
    return statSync(p).isDirectory() ? walk(p) : p.endsWith('.tsx') ? [p] : []
  })
}

const viFlat = flatten(vi as Tree)
const enFlat = flatten(en as Tree)

describe('i18n', () => {
  it('TC-SC-010-01: vi và en có cùng tập khóa', () => {
    expect(Object.keys(enFlat).sort()).toEqual(Object.keys(viFlat).sort())
  })

  it('TC-SC-010-02: không có bản dịch rỗng', () => {
    for (const [k, v] of [...Object.entries(viFlat), ...Object.entries(enFlat)]) {
      expect(v.trim(), k).not.toBe('')
    }
  })

  it('TC-FR-061-06: mọi mã lỗi backend có thông báo ở cả hai ngôn ngữ', () => {
    for (const code of Object.keys(errorCodes)) {
      expect(viFlat[`errors.${code}`], `vi errors.${code}`).toBeTruthy()
      expect(enFlat[`errors.${code}`], `en errors.${code}`).toBeTruthy()
    }
  })

  it('TC-FR-060-01: không có chuỗi giao diện hard-code trong JSX', () => {
    const allowed = new Set(['NichePilot', 'VI', 'EN', '—', '/', '·', '…'])
    const offenders: string[] = []
    const visit = (node: unknown, file: string): void => {
      if (Array.isArray(node)) return node.forEach((n) => visit(n, file))
      if (!node || typeof node !== 'object') return
      const n = node as { type?: string; value?: unknown }
      if (n.type === 'JSXText' && typeof n.value === 'string') {
        const text = n.value.trim()
        if (/[A-Za-zÀ-ỹ]/.test(text) && !allowed.has(text)) offenders.push(`${file}: ${text}`)
      }
      for (const v of Object.values(node)) if (v && typeof v === 'object') visit(v, file)
    }
    for (const file of walk(join(__dirname, '../../src'))) {
      const { program } = parseSync(file, readFileSync(file, 'utf8'))
      visit(program, file)
    }
    expect(offenders).toEqual([])
  })

  it('TC_E1_FR026_04: mọi khóa discovery.* dùng trong mã có VI/EN (gồm khóa động theo enum)', () => {
    const files = [...walk(join(__dirname, '../../src')), join(__dirname, '../../src/api/discovery.ts')]
    const used = new Set<string>()
    for (const file of files) {
      for (const m of readFileSync(file, 'utf8').matchAll(/t\(\s*'(discovery\.[a-zA-Z0-9_.]+)'/g)) used.add(m[1])
    }
    const dynamic: Record<string, string[]> = {
      'discovery.verification': ['VERIFIED', 'INFERRED', 'UNKNOWN', 'CONFLICTING'],
      'discovery.evidenceStatus': ['EVIDENCE_SUFFICIENT', 'INSUFFICIENT_EVIDENCE'],
      'discovery.monetization': ['SIGNALS_FOUND', 'MONETIZATION_UNVERIFIED', 'NO_AFFILIATE_FOUND'],
      'discovery.decision.status': ['CANDIDATE', 'WATCH', 'PURSUE', 'REJECTED', 'HIDDEN'],
      'discovery.ranking.list': ['research', 'affiliate', 'needs_research'],
      'discovery.ranking.rec': ['PURSUE', 'REJECT', 'UNKNOWN'],
      'discovery.ranking.criteria': ['problem_severity', 'monetization', 'market_gap', 'reachability', 'competition_opportunity', 'demand_stability'],
      'discovery.finding': ['CURRENT_SOLUTIONS', 'MARKET_GAPS', 'POTENTIAL_PRODUCTS', 'MONETIZATION', 'CHANNELS', 'RISKS'],
      'discovery.persona': ['segment', 'context', 'goals', 'obstacles', 'ability_to_pay'],
      'discovery.competitorKind': ['PRODUCT', 'SERVICE', 'MANUAL_WORKAROUND'],
      'discovery.outcome': ['COMPLETED', 'PARTIAL_COMPLETED'],
      'discovery.stopReason': ['ALL_CANDIDATES_SUFFICIENT', 'CANDIDATES_EXHAUSTED', 'TIME_LIMIT_REACHED', 'PAGE_LIMIT_REACHED', 'NO_COMPLIANT_SEARCH_SOURCE', 'SOURCES_UNAVAILABLE', 'CANCELLED'],
    }
    for (const [prefix, values] of Object.entries(dynamic)) for (const v of values) used.add(`${prefix}.${v}`)
    used.add('discovery.disclaimer.evidence_not_profitability')
    expect(used.size).toBeGreaterThan(80)
    for (const key of used) {
      expect(viFlat[key], `vi ${key}`).toBeTruthy()
      expect(enFlat[key], `en ${key}`).toBeTruthy()
    }
  })
})

