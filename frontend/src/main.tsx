import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.tsx'
import { initTokenService } from '@/features/auth/services/tokenService'
import { getAuthToken, refreshAccessToken } from '@/shared/services/authBridge'
import { defaultStorage, installOfflineQueue } from '@/shared/services/offlineQueue'
import { toast } from 'sonner'

initTokenService()
installOfflineQueue({
  storage: defaultStorage,
  getToken: getAuthToken,
  refreshToken: refreshAccessToken,
  onError: () => toast.error('离线操作重放失败，请稍后重试'),
  onFlush: (result) => {
    if (result.replayed > 0) toast.success(`已同步 ${result.replayed} 个离线操作`)
  },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
