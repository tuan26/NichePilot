// E4 FR-005 – mục menu điều hướng chung và quy tắc đánh dấu trang hiện tại.
export const NAV_ITEMS: { to: string; key: string; match: (path: string) => boolean }[] = [
  { to: '/overview', key: 'overview', match: (p) => p === '/overview' },
  { to: '/niches', key: 'niches', match: (p) => p === '/niches' || (p.startsWith('/niches/') && !/\/(products|keywords)/.test(p)) },
  { to: '/products', key: 'products', match: (p) => p === '/products' || /^\/niches\/[^/]+\/products/.test(p) },
  { to: '/keywords', key: 'keywords', match: (p) => p === '/keywords' || /^\/niches\/[^/]+\/keywords/.test(p) },
  { to: '/jobs', key: 'jobs', match: (p) => p.startsWith('/jobs') || p === '/discovery/runs' },
  { to: '/costs', key: 'costs', match: (p) => p === '/costs' },
  { to: '/settings', key: 'settings', match: (p) => p === '/settings' },
  { to: '/sources', key: 'sources', match: (p) => p === '/sources' },
  { to: '/', key: 'status', match: (p) => p === '/' },
]
