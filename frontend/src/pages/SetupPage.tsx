// Trang khởi tạo tài khoản chủ sở hữu lần đầu (T055 – US1 kịch bản 2).
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { type FormEvent, useState } from 'react'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router'
import { api, errorKey } from '@/api/client'
import type { Me } from '@/api/types'
import { Layout } from '@/app/Layout'
import { Button } from '@/components/ui/button'
import { Alert, Card, Input, Label } from '@/components/ui/form'
import { currentLocale } from '@/i18n'

export function SetupPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [localError, setLocalError] = useState<string | null>(null)

  const setup = useMutation({
    mutationFn: () =>
      api<Me>('/api/v1/auth/setup', { method: 'POST', body: { username, password, ui_locale: currentLocale() } }),
    onSuccess: async () => {
      await qc.invalidateQueries()
      void navigate('/', { replace: true })
    },
  })

  function submit(e: FormEvent) {
    e.preventDefault()
    if (password !== confirm) {
      setLocalError('setup.passwordMismatch')
      return
    }
    setLocalError(null)
    setup.mutate()
  }

  return (
    <Layout>
      <Card className="mx-auto max-w-md">
        <h1 className="text-xl font-semibold">{t('setup.title')}</h1>
        <p className="mt-1 text-sm text-slate-600">{t('setup.description')}</p>
        <form className="mt-6 space-y-4" onSubmit={submit} noValidate>
          <div className="space-y-1">
            <Label htmlFor="username">{t('setup.username')}</Label>
            <Input id="username" autoComplete="username" value={username} onChange={(e) => setUsername(e.target.value)} />
            <p className="text-xs text-slate-500">{t('setup.usernameHint')}</p>
          </div>
          <div className="space-y-1">
            <Label htmlFor="password">{t('setup.password')}</Label>
            <Input id="password" type="password" autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} />
            <p className="text-xs text-slate-500">{t('setup.passwordHint')}</p>
          </div>
          <div className="space-y-1">
            <Label htmlFor="confirm">{t('setup.confirmPassword')}</Label>
            <Input id="confirm" type="password" autoComplete="new-password" value={confirm} onChange={(e) => setConfirm(e.target.value)} />
          </div>
          {(localError || setup.error) && <Alert>{t(localError ?? errorKey(setup.error))}</Alert>}
          <Button type="submit" className="w-full" disabled={setup.isPending}>
            {setup.isPending ? t('app.loading') : t('setup.submit')}
          </Button>
        </form>
      </Card>
    </Layout>
  )
}
