// E4 – xuất CSV an toàn (FR-020, research R-05): UTF-8 BOM để Excel đọc đúng tiếng Việt, quote theo RFC 4180, vô hiệu hóa công thức
// ở ô bắt đầu bằng = + - @ tab CR (chống CSV injection). Giá trị null/undefined → "UNKNOWN" (không bịa dữ liệu).
export type CsvCell = string | number | boolean | null | undefined

const FORMULA_START = /^[=+\-@\t\r]/
export const UNKNOWN = 'UNKNOWN'

export function csvCell(value: CsvCell): string {
  let s = value === null || value === undefined ? UNKNOWN : String(value)
  if (FORMULA_START.test(s)) s = `'${s}`
  return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
}

export function toCsv(headers: string[], rows: CsvCell[][]): string {
  const lines = [headers, ...rows].map((r) => r.map(csvCell).join(','))
  return `﻿${lines.join('\r\n')}\r\n`
}

export function downloadCsv(filename: string, csv: string): void {
  const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}
