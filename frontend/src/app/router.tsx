// Router (T054).
import { createBrowserRouter, Navigate } from 'react-router'
import { RequireAuth, SetupGate } from '@/app/guards'
import { DiscoveryRunsPage } from '@/pages/discovery/DiscoveryRunsPage'
import { NicheDetailPage } from '@/pages/discovery/NicheDetailPage'
import { LoginPage } from '@/pages/LoginPage'
import { StatusPage } from '@/pages/StatusPage'

export const router = createBrowserRouter([
  {
    path: '/',
    element: (
      <RequireAuth>
        <StatusPage />
      </RequireAuth>
    ),
  },
  {
    path: '/discovery/runs',
    element: (
      <RequireAuth>
        <DiscoveryRunsPage />
      </RequireAuth>
    ),
  },
  {
    path: '/niches/:nicheId',
    element: (
      <RequireAuth>
        <NicheDetailPage />
      </RequireAuth>
    ),
  },
  { path: '/setup', element: <SetupGate /> },
  { path: '/login', element: <LoginPage /> },
  { path: '*', element: <Navigate to="/" replace /> },
])
