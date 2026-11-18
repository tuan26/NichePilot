// Router (T054).
import { createBrowserRouter, Navigate } from 'react-router'
import { RequireAuth, SetupGate } from '@/app/guards'
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
  { path: '/setup', element: <SetupGate /> },
  { path: '/login', element: <LoginPage /> },
  { path: '*', element: <Navigate to="/" replace /> },
])
