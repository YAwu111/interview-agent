import { flushSync } from 'react-dom'
import { useThemeStore, type ThemeMode } from './themeStore'

/** 以 origin 元素中心为圆心，圆形揭示切换到 next；不支持 View Transitions 或减动效时瞬时切换 */
export function switchTheme(next: ThemeMode, origin: HTMLElement | null) {
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  if (reduce || !origin || !document.startViewTransition) {
    useThemeStore.getState().set(next)
    return
  }
  const rect = origin.getBoundingClientRect()
  const x = rect.left + rect.width / 2
  const y = rect.top + rect.height / 2
  // 半径 = 到最远视口角的距离，保证圆最终盖住全屏
  const r = Math.hypot(Math.max(x, innerWidth - x), Math.max(y, innerHeight - y))
  const root = document.documentElement.style
  root.setProperty('--theme-x', `${x}px`)
  root.setProperty('--theme-y', `${y}px`)
  root.setProperty('--theme-r', `${r}px`)
  // flushSync 强制 ThemeProvider 的 effect 在回调内同步执行（.dark class 翻转），
  // 浏览器才能截到"新主题"快照
  document.startViewTransition(() => flushSync(() => useThemeStore.getState().set(next)))
}
