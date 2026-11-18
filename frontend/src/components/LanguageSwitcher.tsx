// Chuyển VI/EN (E4-03, E4-04): đổi ngay không tải lại; lưu localStorage và đồng bộ hồ sơ khi đã đăng nhập.
import { useTranslation } from 'react-i18next'
import { api } from '@/api/client'
import { Button } from '@/components/ui/button'
import { currentLocale, type Locale } from '@/i18n'

export function LanguageSwitcher({ syncProfile = false }: { syncProfile?: boolean }) {
  const { t, i18n } = useTranslation()
  const active = currentLocale()

  async function choose(locale: Locale) {
    await i18n.changeLanguage(locale)
    if (syncProfile) {
      await api('/api/v1/auth/me', { method: 'PATCH', body: { ui_locale: locale } }).catch(() => undefined)
    }
  }

  return (
    <div className="flex items-center gap-1" role="group" aria-label={t('language.label')}>
      {(['vi', 'en'] as const).map((l) => (
        <Button
          key={l}
          size="sm"
          variant={active === l ? 'default' : 'ghost'}
          aria-pressed={active === l}
          title={t(`language.${l}`)}
          onClick={() => void choose(l)}
        >
          {l.toUpperCase()}
        </Button>
      ))}
    </div>
  )
}
