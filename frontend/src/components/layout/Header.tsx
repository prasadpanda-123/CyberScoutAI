import { useState } from "react"
import { useLocation, useNavigate } from "react-router-dom"
import { Bell, Compass, Menu, ShieldCheck, User } from "lucide-react"
import { useAuth } from "@/lib/auth-context"
import { Button } from "@/components/ui/button"

const routeTitles: Record<string, string> = {
  "/": "Overview",
  "/dashboard": "Dashboard",
  "/opportunities": "Explore Opportunities",
  "/saved": "Saved Opportunities",
  "/notifications": "Notifications",
  "/profile": "Profile & Security",
  "/admin": "Command Center",
  "/admin/dashboard": "Command Center",
  "/admin/collectors": "AI Discovery Collectors",
  "/admin/data-quality": "Data Quality & Quarantine",
  "/admin/scheduler": "Pipeline Scheduler",
  "/admin/analytics": "Platform Analytics",
  "/admin/logs": "Audit & System Logs",
  "/admin/users": "User Access Management",
  "/app": "Dashboard",
  "/app/dashboard": "Dashboard",
  "/app/opportunities": "Explore Opportunities",
  "/app/saved": "Saved Opportunities",
  "/app/notifications": "Notifications",
  "/app/profile": "Profile & Security",
  "/app/admin": "Command Center",
  "/app/admin/dashboard": "Command Center",
  "/app/admin/collectors": "AI Discovery Collectors",
  "/app/admin/data-quality": "Data Quality & Quarantine",
  "/app/admin/scheduler": "Pipeline Scheduler",
  "/app/admin/analytics": "Platform Analytics",
  "/app/admin/logs": "Audit & System Logs",
  "/app/admin/users": "User Access Management",
}

interface HeaderProps {
  onOpenMobile: () => void
}

export function Header({ onOpenMobile }: HeaderProps) {
  const location = useLocation()
  const navigate = useNavigate()
  const { user } = useAuth()
  const [dropdownOpen, setDropdownOpen] = useState(false)

  const currentTitle = routeTitles[location.pathname] || "CyberScout AI"

  return (
    <header className="h-16 border-b border-border/80 bg-card/95 backdrop-blur px-4 md:px-7 flex items-center justify-between sticky top-0 z-20 shadow-[0_1px_8px_rgba(0,0,0,0.2)]">
      <div className="flex items-center space-x-3">
        <Button
          variant="ghost"
          size="icon"
          onClick={onOpenMobile}
          className="md:hidden h-9 w-9 text-muted-foreground"
          aria-label="Open navigation"
        >
          <Menu className="h-5 w-5" />
        </Button>
        <div className="flex items-center space-x-2">
          <h1 className="text-base md:text-lg font-semibold tracking-tight text-foreground">
            {currentTitle}
          </h1>
          {user?.is_admin && (location.pathname.startsWith("/admin") || location.pathname.startsWith("/app/admin")) && (
            <span className="inline-flex items-center gap-1 rounded-full bg-cyber-blue/10 px-2 py-0.5 text-xs font-medium text-cyber-blue border border-cyber-blue/20">
              <ShieldCheck className="h-3 w-3" /> Admin
            </span>
          )}
        </div>
      </div>

      <div className="flex items-center space-x-2 sm:space-x-4">
        <button
          onClick={() => navigate(location.pathname.startsWith("/app") ? "/app/opportunities" : "/opportunities")}
          className="hidden sm:flex items-center space-x-2 rounded-lg border border-border bg-muted/50 px-3 py-2 text-xs text-muted-foreground hover:bg-muted transition-colors w-44 md:w-56"
          aria-label="Browse opportunities"
        >
          <Compass className="h-3.5 w-3.5" />
          <span className="flex-1 text-left truncate">Browse opportunities</span>
        </button>

        <Button
          variant="ghost"
          size="icon"
          onClick={() => navigate(location.pathname.startsWith("/app") ? "/app/notifications" : "/notifications")}
          className="relative h-9 w-9 text-muted-foreground hover:text-foreground"
          title="Notifications"
          aria-label="View notifications"
        >
          <Bell className="h-4 w-4" />
        </Button>

        <div className="relative">
          <button
            onClick={() => setDropdownOpen(!dropdownOpen)}
            className="flex items-center space-x-2 rounded-full border border-border p-1 focus:outline-none focus:ring-2 focus:ring-ring"
            aria-label="Open account menu"
            aria-expanded={dropdownOpen}
          >
            <div className="h-8 w-8 rounded-full bg-primary/10 text-primary flex items-center justify-center font-bold text-xs">
              {user?.username?.substring(0, 1).toUpperCase() || "U"}
            </div>
          </button>

          {dropdownOpen && (
            <>
              <div
                className="fixed inset-0 z-40"
                onClick={() => setDropdownOpen(false)}
              />
              <div className="absolute right-0 mt-2 w-52 rounded-md border bg-card p-1 shadow-lg z-50 animate-in fade-in-50 zoom-in-95">
                <div className="px-3 py-2 border-b mb-1">
                  <p className="text-xs font-medium text-foreground truncate">
                    {user?.username}
                  </p>
                  <p className="text-[11px] text-muted-foreground truncate">
                    {user?.email || "Signed In"}
                  </p>
                </div>
                <button
                  onClick={() => {
                    navigate(location.pathname.startsWith("/app") ? "/app/profile" : "/profile")
                    setDropdownOpen(false)
                  }}
                  className="w-full flex items-center space-x-2 px-3 py-2 text-xs rounded hover:bg-muted text-foreground transition-colors text-left"
                >
                  <User className="h-3.5 w-3.5 text-muted-foreground" />
                  <span>Account & Settings</span>
                </button>
                {user?.is_admin && (
                  <button
                    onClick={() => {
                      navigate(location.pathname.startsWith("/app") ? "/app/admin/dashboard" : "/admin/dashboard")
                      setDropdownOpen(false)
                    }}
                    className="w-full flex items-center space-x-2 px-3 py-2 text-xs rounded hover:bg-muted text-cyber-blue transition-colors text-left font-medium"
                  >
                    <ShieldCheck className="h-3.5 w-3.5 text-cyber-blue" />
                    <span>Command Center</span>
                  </button>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </header>
  )
}

