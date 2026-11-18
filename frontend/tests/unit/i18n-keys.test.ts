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
})
