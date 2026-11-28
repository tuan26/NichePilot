// T008 – xuất CSV an toàn (FR-020, SC-006): BOM UTF-8, quote RFC 4180, vô hiệu hóa công thức, UNKNOWN cho giá trị thiếu.
// Test case: TC_E4_FR020_01, TC_E4_SC006_01.
import { describe, expect, it } from 'vitest'
import type { KeywordItem } from '../../src/api/types'
import i18n from '../../src/i18n'
import { csvCell, toCsv } from '../../src/lib/csv'
import { keywordsCsv } from '../../src/lib/exports'

describe('TC_E4_FR020_01 CSV', () => {
  it('BOM, CRLF, quote, tiếng Việt', () => {
    const csv = toCsv(['Tên', 'Ghi chú'], [['Tiệm bánh "nhỏ"', 'a,b'], ['dòng\nmới', 1.5]])
    expect(csv.startsWith('﻿')).toBe(true)
    expect(csv).toContain('"Tiệm bánh ""nhỏ"""')
    expect(csv).toContain('"a,b"')
    expect(csv).toContain('"dòng\nmới",1.5\r\n')
  })

  it('TC_E4_SC006_01 vô hiệu hóa công thức và giữ UNKNOWN', () => {
    for (const bad of ['=HYPERLINK("x")', '+1', '-2+3', '@SUM(A1)', '\tx', '\rx']) {
      expect(csvCell(bad).replace(/^"/, '').startsWith("'")).toBe(true)
    }
    expect(csvCell(null)).toBe('UNKNOWN')
    expect(csvCell(undefined)).toBe('UNKNOWN')
    expect(csvCell(0)).toBe('0')
  })

  it('keyword: chỉ số không nguồn → UNKNOWN, tiêu đề theo ngôn ngữ', async () => {
    await i18n.changeLanguage('vi')
    const kw = {
      text: 'how to stop running out of flour',
      intent: 'INFORMATIONAL',
      length_class: 'LONG_TAIL',
      metrics: {
        search_volume: { value: 900, source: null, collected_at: null, market: null },
        cpc: { value: null, source: null, collected_at: null, market: null },
        keyword_difficulty: { value: null, source: null, collected_at: null, market: null },
      },
      evaluation: null,
      data_origin: 'MOCK',
    } as unknown as KeywordItem
    const csv = keywordsCsv([kw], i18n.t)
    expect(csv.split('\r\n')[0]).toContain('Nguồn dữ liệu')
    expect(csv).toContain('how to stop running out of flour,INFORMATIONAL,LONG_TAIL,UNKNOWN,UNKNOWN,UNKNOWN,UNKNOWN,UNKNOWN,MOCK')
  })
})
