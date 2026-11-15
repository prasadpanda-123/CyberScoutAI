export type Theme = "dark" | "light"

const THEME_STORAGE_KEY = "cyberscout-theme"
const THEME_MODE_STORAGE_KEY = "cyberscout-theme-mode"

export function getInitialTheme(): Theme {
  try {
    return window.localStorage.getItem(THEME_STORAGE_KEY) === "light" ? "light" : "dark"
  } catch {
    return "dark"
  }
}

export function applyTheme(theme: Theme, persist = false) {
  const root = document.documentElement
  root.dataset.theme = theme
  root.classList.toggle("dark", theme === "dark")

  if (persist) {
    try {
      window.localStorage.setItem(THEME_STORAGE_KEY, theme)
      window.localStorage.setItem(THEME_MODE_STORAGE_KEY, theme)
    } catch {
      // The current page still changes theme when storage is unavailable.
    }
  }
}
