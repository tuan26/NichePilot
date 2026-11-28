// i18n (T052 – FR-060, E4-01…E4-06): tiếng Việt mặc định, ghi nhớ lựa chọn, định dạng theo locale.
import i18n from 'i18next'
import LanguageDetector from 'i18next-browser-languagedetector'
import { initReactI18next } from 'react-i18next'
import en from './locales/en.json'
import vi from './locales/vi.json'

export const SUPPORTED_LOCALES = ['vi', 'en'] as const
export type Locale = (typeof SUPPORTED_LOCALES)[number]
export const LOCALE_STORAGE_KEY = 'np.locale'

void i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: { vi: { translation: vi }, en: { translation: en } },
    fallbackLng: 'vi', // E4-02: mặc định tiếng Việt (không theo ngôn ngữ trình duyệt)
    supportedLngs: SUPPORTED_LOCALES,
    nonExplicitSupportedLngs: false,
    detection: { order: ['localStorage'], lookupLocalStorage: LOCALE_STORAGE_KEY, caches: ['localStorage'] },
    interpolation: { escapeValue: false },
  })

export function currentLocale(): Locale {
  return i18n.resolvedLanguage === 'en' ? 'en' : 'vi'
}

const INTL_LOCALE: Record<Locale, string> = { vi: 'vi-VN', en: 'en-US' }

export function formatDateTime(value: string | Date, locale: Locale = currentLocale()): string {
  const d = typeof value === 'string' ? new Date(value) : value
  return new Intl.DateTimeFormat(INTL_LOCALE[locale], { dateStyle: 'medium', timeStyle: 'short' }).format(d)
}

export function formatNumber(value: number, locale: Locale = currentLocale()): string {
  return new Intl.NumberFormat(INTL_LOCALE[locale]).format(value)
}

/** Tiền USD theo locale (E4-06); chi phí AI dùng tới 6 chữ số thập phân nên giữ tối đa 6, tối thiểu 2. */
export function formatMoney(value: number | string, locale: Locale = currentLocale()): string {
  const n = typeof value === 'string' ? Number(value) : value
  return new Intl.NumberFormat(INTL_LOCALE[locale], {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 6,
  }).format(n)
}

/** Phần trăm từ tỉ lệ 0–1 (E4-06). */
export function formatPercent(ratio: number, locale: Locale = currentLocale()): string {
  return new Intl.NumberFormat(INTL_LOCALE[locale], { style: 'percent', maximumFractionDigits: 1 }).format(ratio)
}

export default i18n
