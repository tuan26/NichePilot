// Điều hướng theo trạng thái khởi tạo/đăng nhập (T054).
import { useQuery } from '@tanstack/react-query'
import type { ReactNode } from 'react'
import { useTranslation } from 'react-i18next'
import { Navigate } from 'react-router'
import { ApiError, api } from '@/api/client'
import type { Me } from '@/api/types'
import { SetupPage } from '@/pages/SetupPage'

function useSetupStatus() {
  return useQuery({
    queryKey: ['setup-status'],
    queryFn: () => api<{ setup_required: boolean }>('/api/v1/auth/setup-status'),
  })
}

function Loading() {
  const { t } = useTranslation()
  return <p className="p-8 text-sm text-slate-500">{t('app.loading')}</p>
}

export function RequireAuth({ children }: { children: ReactNode }) {
  const setup = useSetupStatus()
  const me = useQuery({
    queryKey: ['me'],
    queryFn: () => api<Me>('/api/v1/auth/me'),
    enabled: setup.data?.setup_required === false,
    retry: false,
  })
  if (setup.isPending) return <Loading />
  if (setup.data?.setup_required) return <Navigate to="/setup" replace />
  if (me.isPending) return <Loading />
  if (me.error instanceof ApiError && me.error.status === 401) return <Navigate to="/login" replace />
  return <>{children}</>
}

export function SetupGate() {
  const setup = useSetupStatus()
  if (setup.isPending) return <Loading />
  return setup.data?.setup_required === false ? <Navigate to="/" replace /> : <SetupPage />
}

