import React, { createContext, useContext, useEffect, useState } from "react"
import { authApi, type MeResponse } from "@/lib/api"

interface AuthContextType {
  user: MeResponse["user"] | null
  isAuthenticated: boolean
  isLoading: boolean
  refresh: () => Promise<void>
  logout: () => Promise<boolean>
}

let pendingMeRequest: Promise<MeResponse> | null = null

function getCurrentSession(): Promise<MeResponse> {
  if (!pendingMeRequest) {
    pendingMeRequest = authApi.me().finally(() => {
      pendingMeRequest = null
    })
  }
  return pendingMeRequest
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  isAuthenticated: false,
  isLoading: true,
  refresh: async () => { },
  logout: async () => false,
})

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<MeResponse["user"] | null>(null)
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false)
  const [isLoading, setIsLoading] = useState<boolean>(true)

  const checkAuth = async () => {
    try {
      const res = await getCurrentSession()
      if (res?.csrf_token) {
        const meta = document.querySelector<HTMLMetaElement>('meta[name="csrf-token"]')
        if (meta) {
          meta.content = res.csrf_token
        }
      }

      if (res && res.authenticated && res.user) {
        setUser(res.user)
        setIsAuthenticated(true)
      } else {
        setUser(null)
        setIsAuthenticated(false)
      }
    } catch {
      setUser(null)
      setIsAuthenticated(false)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    checkAuth()
  }, [])

  const logout = async () => {
    try {
      const response = await authApi.logout()
      if (response?.status !== "success") {
        throw new Error("The server did not confirm logout.")
      }
    } catch (e) {
      console.error("Logout error", e)
      return false
    }
    setUser(null)
    setIsAuthenticated(false)
    const csrfMeta = document.querySelector<HTMLMetaElement>('meta[name="csrf-token"]')
    if (csrfMeta) {
      csrfMeta.content = ""
    }
    window.location.href = "/app/login"
    return true
  }

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated,
        isLoading,
        refresh: checkAuth,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
