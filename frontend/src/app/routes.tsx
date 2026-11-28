// Router (T054).
import { Navigate, type RouteObject } from 'react-router'
import { RequireAuth, SetupGate } from '@/app/guards'
import { DiscoveryRunsPage } from '@/pages/discovery/DiscoveryRunsPage'
import { NicheDetailPage } from '@/pages/discovery/NicheDetailPage'
import { NicheRankingPage } from '@/pages/discovery/NicheRankingPage'
import { SourcesPage } from '@/pages/discovery/SourcesPage'
import { LoginPage } from '@/pages/LoginPage'
import { CostsPage } from '@/pages/dashboard/CostsPage'
import { JobDetailPage } from '@/pages/dashboard/JobDetailPage'
import { JobsPage } from '@/pages/dashboard/JobsPage'
import { OverviewPage } from '@/pages/dashboard/OverviewPage'
import { ResearchNichesPage } from '@/pages/dashboard/ResearchNichesPage'
import { SettingsPage } from '@/pages/dashboard/SettingsPage'
import { KeywordClusterPage } from '@/pages/keywords/KeywordClusterPage'
import { NicheKeywordsPage } from '@/pages/keywords/NicheKeywordsPage'
import { NicheProductsPage } from '@/pages/products/NicheProductsPage'
import { ProductDetailPage } from '@/pages/products/ProductDetailPage'
import { StatusPage } from '@/pages/StatusPage'

export const routes: RouteObject[] = [
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
  {
    path: '/niches/:nicheId/keywords',
    element: (
      <RequireAuth>
        <NicheKeywordsPage />
      </RequireAuth>
    ),
  },
  {
    path: '/niches/:nicheId/keywords/:clusterId',
    element: (
      <RequireAuth>
        <KeywordClusterPage />
      </RequireAuth>
    ),
  },
  {
    path: '/overview',
    element: (
      <RequireAuth>
        <OverviewPage />
      </RequireAuth>
    ),
  },
  {
    path: '/products',
    element: (
      <RequireAuth>
        <ResearchNichesPage mode="products" />
      </RequireAuth>
    ),
  },
  {
    path: '/keywords',
    element: (
      <RequireAuth>
        <ResearchNichesPage mode="keywords" />
      </RequireAuth>
    ),
  },
  {
    path: '/jobs',
    element: (
      <RequireAuth>
        <JobsPage />
      </RequireAuth>
    ),
  },
  {
    path: '/jobs/:jobId',
    element: (
      <RequireAuth>
        <JobDetailPage />
      </RequireAuth>
    ),
  },
  {
    path: '/costs',
    element: (
      <RequireAuth>
        <CostsPage />
      </RequireAuth>
    ),
  },
  {
    path: '/settings',
    element: (
      <RequireAuth>
        <SettingsPage />
      </RequireAuth>
    ),
  },
  { path: '/setup', element: <SetupGate /> },
  { path: '/login', element: <LoginPage /> },
  { path: '*', element: <Navigate to="/" replace /> },
]
