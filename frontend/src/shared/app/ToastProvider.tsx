import { Toaster } from '@/components/ui/sonner'
import { useThemeStore } from '@/features/settings/app/themeStore'

/** 全局 toast，主题跟随 themeStore */
export function ToastProvider() {
  const mode = useThemeStore((s) => s.mode)
  return <Toaster theme={mode} position="top-center" richColors />
}
