import { createBrowserRouter } from 'react-router-dom'
import { AppLayout } from '@/components/AppLayout'
import { AuthLayout } from '@/features/auth/AuthLayout'
import { ProtectedRoute } from '@/components/ProtectedRoute'
import { AcceptInvitePage } from '@/pages/AcceptInvitePage'
import { ApiKeysPage } from '@/pages/ApiKeysPage'
import { DashboardPage } from '@/pages/DashboardPage'
import { ChannelsPage } from '@/pages/ChannelsPage'
import { IncidentDetailPage } from '@/pages/IncidentDetailPage'
import { IncidentsPage } from '@/pages/IncidentsPage'
import { HealthPage } from '@/pages/HealthPage'
import { LoginPage } from '@/pages/LoginPage'
import { MonitorDetailPage } from '@/pages/MonitorDetailPage'
import { MonitorsPage } from '@/pages/MonitorsPage'
import { NewMonitorPage } from '@/pages/NewMonitorPage'
import { NewOrgPage } from '@/pages/NewOrgPage'
import { NotFoundPage } from '@/pages/NotFoundPage'
import { OAuthCallbackPage } from '@/pages/OAuthCallbackPage'
import { OrgListPage } from '@/pages/OrgListPage'
import { OrgMembersPage } from '@/pages/OrgMembersPage'
import { PublicStatusPage } from '@/pages/PublicStatusPage'
import { StatusPagesPage } from '@/pages/StatusPagesPage'
import { RegisterPage } from '@/pages/RegisterPage'

export const router = createBrowserRouter([
  // Public, and deliberately OUTSIDE AuthLayout: no session bootstrap, no
  // /auth/refresh, nothing that assumes a logged-in user.
  { path: '/status/:slug', element: <PublicStatusPage /> },

  {
    element: <AuthLayout />,
    children: [
      // Reachable without a session, but still session-aware.
      { path: '/login', element: <LoginPage /> },
      { path: '/register', element: <RegisterPage /> },
      { path: '/auth/callback', element: <OAuthCallbackPage /> },
      { path: '/health', element: <HealthPage /> },

      // Needs a session but no org context — the invite itself names the org.
      { path: '/invites/:token', element: <AcceptInvitePage /> },

      {
        element: <ProtectedRoute />,
        children: [
          {
            element: <AppLayout />,
            children: [
              { path: '/', element: <OrgListPage /> },
              { path: '/orgs/new', element: <NewOrgPage /> },
              { path: '/orgs/:orgId', element: <DashboardPage /> },
              { path: '/orgs/:orgId/members', element: <OrgMembersPage /> },
              { path: '/orgs/:orgId/monitors', element: <MonitorsPage /> },
              { path: '/orgs/:orgId/monitors/new', element: <NewMonitorPage /> },
              { path: '/orgs/:orgId/monitors/:monitorId', element: <MonitorDetailPage /> },
              { path: '/orgs/:orgId/incidents', element: <IncidentsPage /> },
              { path: '/orgs/:orgId/incidents/:incidentId', element: <IncidentDetailPage /> },
              { path: '/orgs/:orgId/channels', element: <ChannelsPage /> },
              { path: '/orgs/:orgId/status-pages', element: <StatusPagesPage /> },
              { path: '/orgs/:orgId/api-keys', element: <ApiKeysPage /> },
            ],
          },
        ],
      },

      { path: '*', element: <NotFoundPage /> },
    ],
  },
])
