import { useState } from "react"
import { Moon, Sun } from "lucide-react"
import { applyTheme, getInitialTheme, type Theme } from "@/lib/theme"
import { cn } from "@/lib/utils"

interface ThemeToggleProps {
  className?: string
}

export function ThemeToggle({ className }: ThemeToggleProps) {
  const [theme, setTheme] = useState<Theme>(getInitialTheme)
  const nextTheme = theme === "dark" ? "light" : "dark"

  const toggleTheme = () => {
    applyTheme(nextTheme, true)
    setTheme(nextTheme)
  }

  return (
    <button
      type="button"
      onClick={toggleTheme}
      aria-label={`Switch to ${nextTheme} mode`}
      aria-pressed={theme === "dark"}
      title={`Switch to ${nextTheme} mode`}
      className={cn(
        "inline-flex h-9 w-9 shrink-0 items-center justify-center gap-2 rounded-lg border border-border bg-card px-0 text-muted-foreground transition-colors hover:bg-accent hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring sm:w-auto sm:px-2.5",
        className,
      )}
    >
      {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
      <span className="hidden text-xs font-medium sm:inline">{nextTheme} mode</span>
      <span className="sr-only">Switch to {nextTheme} mode</span>
    </button>
  )
}
