import { createBrowserRouter, Navigate } from 'react-router-dom'
import { AppShell } from '../ui/AppShell'
import { AuthGuard } from './AuthGuard'
import { LoginPage } from '@/features/auth/ui/LoginPage'
import { RegisterPage } from '@/features/auth/ui/RegisterPage'
import { OAuthCallbackPage } from '@/features/auth/ui/OAuthCallbackPage'
import { ChatWorkspace } from '@/features/chat/ui/ChatWorkspace'
import { KnowledgePage } from '@/features/knowledge/ui/KnowledgePage'
import { ResourcePage } from '@/features/resources/ui/ResourcePage'
import { SettingsPage } from '@/features/settings/ui/SettingsPage'

export const router = createBrowserRouter([
  { path: '/login', element: <LoginPage /> },
  { path: '/register', element: <RegisterPage /> },
  { path: '/oauth/callback', element: <OAuthCallbackPage /> },
  {
    element: (
      <AuthGuard>
        <AppShell />
      </AuthGuard>
    ),
    children: [
      { path: '/', element: <ChatWorkspace /> },
      { path: '/knowledge', element: <KnowledgePage /> },
      { path: '/resources', element: <ResourcePage /> },
      { path: '/settings', element: <SettingsPage /> },
    ],
  },
  { path: '*', element: <Navigate to="/" replace /> },
])
