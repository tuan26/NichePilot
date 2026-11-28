import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Link, useLocation } from 'react-router'
import { NAV_ITEMS } from '@/app/nav'
import { LanguageSwitcher } from '@/components/LanguageSwitcher'

// E4 FR-005: menu điều hướng chung cho mọi trang sau đăng nhập (trang đăng nhập/khởi tạo không có menu).

export function MainNav({ pathname }: { pathname: string }) {
  const { t } = useTranslation()
  return (
    <nav aria-label={t('nav.label')} className="border-b border-slate-200 bg-white" data-testid="main-nav">
      <ul className="mx-auto flex max-w-5xl flex-wrap gap-1 px-4 py-2 text-sm">
        {NAV_ITEMS.map((item) => {
          const active = item.match(pathname)
          return (
            <li key={item.key}>
              <Link
                to={item.to}
                aria-current={active ? 'page' : undefined}
                className={`rounded-md px-2 py-1 ${active ? 'bg-slate-900 text-white' : 'text-slate-700 hover:bg-slate-100'}`}
                data-testid={`nav-${item.key}`}
              >
                {t(`nav.${item.key}`)}
              </Link>
            </li>
          )
        })}
      </ul>
    </nav>
  )
}

function CurrentNav() {
  const { pathname } = useLocation()
  return <MainNav pathname={pathname} />
}

export function Layout({
  children,
  actions,
  syncProfile = false,
  nav = syncProfile,
}: {
  children: ReactNode
  actions?: ReactNode
  syncProfile?: boolean
  nav?: boolean
}) {
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
      {nav && <CurrentNav />}
      <main className="mx-auto max-w-5xl px-4 py-8">{children}</main>
    </div>
  )
}
