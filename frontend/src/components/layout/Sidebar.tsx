import { useState } from "react"
import { NavLink, useNavigate } from "react-router-dom"
import {
  Compass,
  Bookmark,
  Bell,
  User,
  Shield,
  Cpu,
  CheckCircle2,
  Calendar,
  BarChart3,
  FileText,
  Users,
  LogOut,
  ChevronLeft,
  ChevronRight,
  Sparkles,
} from "lucide-react"
import { useAuth } from "@/lib/auth-context"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { useToast } from "@/components/ui/toast"

interface NavItem {
  name: string
  to: string
  icon: any
}

interface SidebarProps {
  onCloseMobile?: () => void
}

export function Sidebar({ onCloseMobile }: SidebarProps) {
  const { user, logout } = useAuth()
  const { toast } = useToast()
  const [collapsed, setCollapsed] = useState(false)
  const navigate = useNavigate()
  const isApp = window.location.pathname.startsWith('/app')
  const prefix = isApp ? '/app' : ''
  const handleLogout = async () => {
    const succeeded = await logout()
    if (!succeeded) {
      toast({
        title: "Logout failed",
        description: "The server could not confirm your session was revoked. Please try again.",
        variant: "destructive",
      })
    }
  }

  const userNavItems: NavItem[] = [
    { name: "Dashboard", to: `${prefix}/dashboard`, icon: Compass },
    { name: "Explore", to: `${prefix}/opportunities`, icon: Sparkles },
    { name: "Saved", to: `${prefix}/saved`, icon: Bookmark },
    { name: "Notifications", to: `${prefix}/notifications`, icon: Bell },
    { name: "Profile", to: `${prefix}/profile`, icon: User },
  ]

  const adminNavItems: NavItem[] = [
    { name: "Command Center", to: `${prefix}/admin/dashboard`, icon: Shield },
    { name: "AI Collectors", to: `${prefix}/admin/collectors`, icon: Cpu },
    { name: "Data Quality", to: `${prefix}/admin/data-quality`, icon: CheckCircle2 },
    { name: "Pipeline Scheduler", to: `${prefix}/admin/scheduler`, icon: Calendar },
    { name: "Analytics", to: `${prefix}/admin/analytics`, icon: BarChart3 },
    { name: "Audit Logs", to: `${prefix}/admin/logs`, icon: FileText },
    { name: "User Management", to: `${prefix}/admin/users`, icon: Users },
  ]

  return (
    <aside
      className={cn(
        "flex flex-col border-r border-border/80 bg-card h-full transition-all duration-300 z-30 select-none shadow-[1px_0_4px_rgba(16,24,40,0.03)]",
        collapsed ? "w-16" : "w-64"
      )}
    >
      <div className="flex h-16 items-center justify-between px-4 border-b">
        <button
          type="button"
          onClick={() => {
            navigate(isApp ? "/app/dashboard" : "/dashboard")
            onCloseMobile?.()
          }}
          className="flex items-center space-x-2.5 overflow-hidden text-left"
          aria-label="Go to dashboard"
        >
          <div className="h-9 w-9 rounded-xl bg-gradient-to-br from-cyber-blue to-cyan-600 flex items-center justify-center text-white font-bold shrink-0 shadow-sm">
            <Shield className="h-5 w-5" />
          </div>
          {!collapsed && (
            <div className="flex flex-col leading-tight">
              <span className="font-bold text-base tracking-tight text-foreground">
                CyberScout<span className="text-cyber-blue">.AI</span>
              </span>
              <span className="text-[10px] uppercase font-mono tracking-wider text-muted-foreground">
                Autonomous Discovery
              </span>
            </div>
          )}
        </button>
        <Button
          variant="ghost"
          size="icon"
          onClick={() => setCollapsed(!collapsed)}
          className="hidden md:flex h-7 w-7 text-muted-foreground hover:text-foreground"
          aria-label={collapsed ? "Expand navigation" : "Collapse navigation"}
        >
          {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
        </Button>
      </div>

      <div className="flex-1 overflow-y-auto px-2 py-4 space-y-6">
        <div className="space-y-1">
          {!collapsed && (
            <p className="px-3 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground mb-2">
              User Portal
            </p>
          )}
          {userNavItems.map((item) => {
            const Icon = item.icon
            return (
              <NavLink
                key={item.to}
                to={item.to}
                onClick={onCloseMobile}
                className={({ isActive }) =>
                  cn(
                    "flex items-center rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                    isActive
                      ? "bg-primary/10 text-primary font-semibold"
                      : "text-muted-foreground hover:bg-muted hover:text-foreground",
                    collapsed && "justify-center px-2"
                  )
                }
                title={collapsed ? item.name : undefined}
              >
                <Icon className={cn("h-4 w-4 shrink-0", !collapsed && "mr-3")} />
                {!collapsed && <span>{item.name}</span>}
              </NavLink>
            )
          })}
        </div>

        {user?.is_admin && (
          <div className="space-y-1 pt-2 border-t">
            {!collapsed && (
              <div className="px-3 mb-2">
                <p className="text-[11px] font-semibold uppercase tracking-wider text-cyber-blue">
                  Admin Console
                </p>
              </div>
            )}
            {adminNavItems.map((item) => {
              const Icon = item.icon
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  onClick={onCloseMobile}
                  className={({ isActive }) =>
                    cn(
                      "flex items-center rounded-lg px-3 py-2.5 text-sm font-medium transition-colors",
                      isActive
                        ? "bg-cyber-blue/15 text-cyber-blue font-semibold"
                        : "text-muted-foreground hover:bg-muted hover:text-foreground",
                      collapsed && "justify-center px-2"
                    )
                  }
                  title={collapsed ? item.name : undefined}
                >
                  <Icon className={cn("h-4 w-4 shrink-0", !collapsed && "mr-3")} />
                  {!collapsed && <span>{item.name}</span>}
                </NavLink>
              )
            })}
          </div>
        )}
      </div>

      <div className="p-3 border-t bg-muted/50">
        <div
          className={cn(
            "flex items-center justify-between",
            collapsed && "flex-col space-y-2 justify-center"
          )}
        >
          <div className={cn("flex items-center space-x-2.5 overflow-hidden", collapsed && "space-x-0")}>
            <div className="h-8 w-8 rounded-full bg-primary/15 text-primary flex items-center justify-center font-bold text-xs shrink-0">
              {user?.username?.substring(0, 2).toUpperCase() || "US"}
            </div>
            {!collapsed && (
              <div className="flex flex-col truncate">
                <span className="text-xs font-semibold truncate text-foreground">
                  {user?.username || "Cyber User"}
                </span>
                <span className="text-[10px] text-muted-foreground truncate font-mono">
                  {user?.role || "Viewer"}
                </span>
              </div>
            )}
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={handleLogout}
            className="h-7 w-7 text-muted-foreground hover:text-destructive"
            title="Log Out"
            aria-label="Log out"
          >
            <LogOut className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </aside>
  )
}

