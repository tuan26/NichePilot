// Router (T054).
import { createBrowserRouter, Navigate } from 'react-router'
import { RequireAuth, SetupGate } from '@/app/guards'
import { DiscoveryRunsPage } from '@/pages/discovery/DiscoveryRunsPage'
import { NicheDetailPage } from '@/pages/discovery/NicheDetailPage'
import { NicheRankingPage } from '@/pages/discovery/NicheRankingPage'
import { SourcesPage } from '@/pages/discovery/SourcesPage'
import { LoginPage } from '@/pages/LoginPage'
import { NicheProductsPage } from '@/pages/products/NicheProductsPage'
import { ProductDetailPage } from '@/pages/products/ProductDetailPage'
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
    path: '/sources',
    element: (
      <RequireAuth>
        <SourcesPage />
      </RequireAuth>
    ),
  },
  {
    path: '/niches',
    element: (
      <RequireAuth>
        <NicheRankingPage />
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
  {
    path: '/niches/:nicheId/products',
    element: (
      <RequireAuth>
        <NicheProductsPage />
      </RequireAuth>
    ),
  },
  {
    path: '/niches/:nicheId/products/:productId',
    element: (
      <RequireAuth>
        <ProductDetailPage />
      </RequireAuth>
    ),
  },
  { path: '/setup', element: <SetupGate /> },
  { path: '/login', element: <LoginPage /> },
  { path: '*', element: <Navigate to="/" replace /> },
])
