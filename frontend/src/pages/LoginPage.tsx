// Trang đăng nhập (T055 – US1 kịch bản 3–4): hiển thị thời điểm hết khóa khi bị khóa tạm.
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router'
import { ApiError, api, errorKey } from '@/api/client'
import type { Me } from '@/api/types'
import { Layout } from '@/app/Layout'
import { Button } from '@/components/ui/button'
import { Alert, Card, Input, Label } from '@/components/ui/form'
import { currentLocale, formatDateTime } from '@/i18n'

export function LoginPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')

  const login = useMutation({
    mutationFn: async () => {
      const me = await api<Me>('/api/v1/auth/login', { method: 'POST', body: { username, password } })
      // Giữ ngôn ngữ người dùng đang chọn trên giao diện và đồng bộ vào hồ sơ.
      if (me.ui_locale !== currentLocale()) {
        await api('/api/v1/auth/me', { method: 'PATCH', body: { ui_locale: currentLocale() } })
      }
      return me
    },
    onSuccess: async () => {
      await qc.invalidateQueries()
      void navigate('/', { replace: true })
    },
  })

  function submit(e: FormEvent) {
    e.preventDefault()
    login.mutate()
  }

  const err = login.error
  const lockedUntil = err instanceof ApiError && err.code === 'AUTH_LOCKED' ? err.params.locked_until : undefined

  return (
    <Layout>
      <Card className="mx-auto max-w-md">
        <h1 className="text-xl font-semibold">{t('login.title')}</h1>
        <p className="mt-1 text-sm text-slate-600">{t('login.description')}</p>
        <form className="mt-6 space-y-4" onSubmit={submit}>
          <div className="space-y-1">
            <Label htmlFor="username">{t('login.username')}</Label>
            <Input id="username" autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)} />
          </div>
          <div className="space-y-1">
            <Label htmlFor="password">{t('login.password')}</Label>
            <Input id="password" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />
          </div>
          {err && (
            <Alert>
              {lockedUntil ? t('login.lockedUntil', { time: formatDateTime(lockedUntil) }) : t(errorKey(err))}
            </Alert>
          )}
          <Button type="submit" className="w-full" disabled={login.isPending}>
            {login.isPending ? t('app.loading') : t('login.submit')}
          </Button>
        </form>
      </Card>
    </Layout>
  )
}
