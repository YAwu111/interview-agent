import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { Moon, Sun, LogOut, Settings as SettingsIcon } from 'lucide-react'
import { Button } from '@/components/ui/button'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Avatar, AvatarFallback } from '@/components/ui/avatar'
import { cn } from '@/lib/utils'
import { useAuth } from '@/features/auth/app/useAuth'
import { useThemeStore } from '@/features/settings/app/themeStore'
import { t } from '@/shared/lib/locale/zh'

const NAV = [
  { to: '/', label: t.nav.chat, end: true },
  { to: '/knowledge', label: t.nav.knowledge },
  { to: '/resources', label: t.nav.resources },
  { to: '/settings', label: t.nav.settings },
]

/** 顶栏 + 内容骨架；聊天页在 Outlet 内自带双栏 */
export function AppShell() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const mode = useThemeStore((s) => s.mode)
  const toggle = useThemeStore((s) => s.toggle)

  return (
    <div className="flex h-svh flex-col bg-background">
      <header className="flex h-14 shrink-0 items-center gap-6 border-b px-4">
        <NavLink to="/" className="flex items-center gap-2">
          <span className="flex size-7 items-center justify-center rounded-md bg-primary text-sm font-semibold text-primary-foreground">
            面
          </span>
          <span className="text-base font-medium">{t.app.name}</span>
        </NavLink>

        <nav className="flex items-center gap-1">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                cn(
                  'rounded-md px-3 py-1.5 text-sm text-muted-foreground transition-colors hover:bg-accent hover:text-foreground',
                  isActive && 'bg-accent font-medium text-foreground',
                )
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <div className="ml-auto flex items-center gap-1">
          <Button
            variant="ghost"
            size="icon"
            onClick={toggle}
            aria-label={t.settings.theme}
          >
            {mode === 'light' ? <Moon /> : <Sun />}
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger
              render={
                <button className="rounded-full outline-none focus-visible:ring-2 focus-visible:ring-ring" />
              }
            >
              <Avatar className="size-8">
                <AvatarFallback className="bg-primary/10 text-xs text-primary">
                  {user?.name?.slice(0, 1) ?? '我'}
                </AvatarFallback>
              </Avatar>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-48">
              <DropdownMenuLabel>
                <div className="flex flex-col">
                  <span className="text-sm">{user?.name}</span>
                  <span className="text-xs font-normal text-muted-foreground">{user?.email}</span>
                </div>
              </DropdownMenuLabel>
              <DropdownMenuSeparator />
              <DropdownMenuItem onClick={() => navigate('/settings')}>
                <SettingsIcon /> {t.nav.settings}
              </DropdownMenuItem>
              <DropdownMenuItem
                onClick={() => {
                  void logout().then(() => navigate('/login', { replace: true }))
                }}
              >
                <LogOut /> {t.auth.logout}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </header>

      <main className="min-h-0 flex-1">
        <Outlet />
      </main>
    </div>
  )
}
