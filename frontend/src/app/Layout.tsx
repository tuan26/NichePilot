import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { LanguageSwitcher } from '@/components/LanguageSwitcher'

export function Layout({ children, actions, syncProfile = false }: { children: ReactNode; actions?: ReactNode; syncProfile?: boolean }) {
  const { t } = useTranslation()
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-3 px-4 py-3">
          <div>
            <p className="text-lg font-semibold">{t('app.name')}</p>
            <p className="text-xs text-slate-500">{t('app.tagline')}</p>
          </div>
          <div className="flex items-center gap-2">
            <LanguageSwitcher syncProfile={syncProfile} />
            {actions}
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-8">{children}</main>
    </div>
  )
}
