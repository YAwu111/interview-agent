import { useEffect } from 'react'
import { useThemeStore } from '@/features/settings/app/themeStore'

/** 把 themeStore 的 mode 同步到 <html> 的 .dark class */
export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const mode = useThemeStore((s) => s.mode)
  useEffect(() => {
    document.documentElement.classList.toggle('dark', mode === 'dark')
  }, [mode])
  return <>{children}</>
}
