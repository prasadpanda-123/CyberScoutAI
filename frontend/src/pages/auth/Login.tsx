import { useState } from "react"
import { Link, useNavigate, useSearchParams } from "react-router-dom"
import { ArrowRight, AlertCircle, CheckCircle2, Compass, Lock, Shield, User } from "lucide-react"
import { authApi } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

export function Login() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const { refresh } = useAuth()
  const isApp = window.location.pathname.startsWith("/app")
  const isAdmin = window.location.pathname.startsWith("/admin")
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)

    try {
      if (isAdmin) {
        const response = await authApi.adminLogin({ username, password })
        if (response?.mfa_required) {
          navigate(isApp ? "/app/admin/verify-otp" : "/admin/verify-otp")
          return
        }
      } else {
        await authApi.login({ username, password })
      }

      await refresh()
      const defaultNext = isAdmin
        ? (isApp ? "/app/admin/dashboard" : "/admin/dashboard")
        : (isApp ? "/app/dashboard" : "/dashboard")
      const requestedNext = searchParams.get("next")
      let next = defaultNext
      if (requestedNext) {
        try {
          const target = new URL(requestedNext, window.location.origin)
          if (target.origin === window.location.origin) {
            next = `${target.pathname}${target.search}${target.hash}`
          }
        } catch {
          next = defaultNext
        }
      }
      navigate(next)
    } catch (err: any) {
      setError(err.message || "Invalid credentials. Please verify your details.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="min-h-screen bg-background lg:grid lg:grid-cols-[1.05fr_0.95fr]">
      <section className="relative hidden min-h-screen overflow-hidden bg-gradient-to-br from-slate-950 via-slate-900 to-blue-950 px-10 py-12 text-white lg:flex lg:flex-col lg:justify-between xl:px-16">
        <div className="pointer-events-none absolute -right-32 top-20 h-96 w-96 rounded-full bg-blue-500/15 blur-3xl" />
        <div className="pointer-events-none absolute -bottom-36 -left-20 h-96 w-96 rounded-full bg-cyan-400/10 blur-3xl" />
        <Link to="/" className="relative flex w-fit items-center gap-3" aria-label="CyberScout AI home">
          <span className="flex h-11 w-11 items-center justify-center rounded-xl bg-white/10 ring-1 ring-white/15">
            <Shield className="h-6 w-6 text-cyan-300" />
          </span>
          <span className="text-lg font-bold tracking-tight">
            CyberScout<span className="text-cyan-300">.AI</span>
            <span className="mt-0.5 block text-[10px] font-medium uppercase tracking-[0.18em] text-slate-300">
              Opportunity intelligence
            </span>
          </span>
        </Link>

        <div className="relative max-w-xl py-12">
          <span className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-3 py-1.5 text-xs font-medium text-slate-200">
            <Compass className="h-3.5 w-3.5 text-cyan-300" />
            A clearer path into cybersecurity
          </span>
          <h1 className="mt-6 text-4xl font-semibold leading-tight tracking-tight xl:text-5xl">
            Find opportunities worth your time.
          </h1>
          <p className="mt-5 max-w-lg text-sm leading-7 text-slate-300 xl:text-base">
            Explore programs, keep a shortlist, and review the details before you apply.
            CyberScout helps make the next step easier to find.
          </p>
          <div className="mt-8 space-y-3">
            {[
              "Browse cybersecurity opportunities",
              "Review cost and eligibility details",
              "Save listings to revisit later",
            ].map((item) => (
              <p key={item} className="flex items-center gap-3 text-sm text-slate-200">
                <CheckCircle2 className="h-4 w-4 text-cyan-300" />
                {item}
              </p>
            ))}
          </div>
        </div>

        <p className="relative text-xs text-slate-400">
          Keep your search focused. Make your next move informed.
        </p>
      </section>

      <section className="flex min-h-screen items-center justify-center px-4 py-10 sm:px-8">
        <div className="w-full max-w-[440px]">
          <Link to="/" className="mb-8 flex items-center justify-center gap-2 lg:hidden">
            <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary text-white">
              <Shield className="h-5 w-5" />
            </span>
            <span className="text-lg font-bold tracking-tight">
              CyberScout<span className="text-cyber-blue">.AI</span>
            </span>
          </Link>

          <div className="mb-6">
            <p className="text-xs font-bold uppercase tracking-[0.14em] text-primary">
              {isAdmin ? "Secure administration" : "Welcome back"}
            </p>
            <h2 className="mt-2 text-3xl font-bold tracking-tight">
              {isAdmin ? "Admin sign in" : "Sign in to your account"}
            </h2>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              {isAdmin
                ? "Use your authorized administrator credentials to continue."
                : "Continue exploring and managing your saved opportunities."}
            </p>
          </div>

          <Card className="border-border/80 shadow-[0_12px_40px_rgba(16,24,40,0.07)]">
            <CardHeader className="space-y-1 pb-4">
              <CardTitle className="text-base">
                {isAdmin ? "Administrative access" : "Account credentials"}
              </CardTitle>
              <CardDescription>
                Your session is protected with server-side authentication.
              </CardDescription>
            </CardHeader>

            <form onSubmit={handleSubmit}>
              <CardContent className="space-y-5">
                {error && (
                  <div
                    role="alert"
                    className="flex items-start gap-2.5 rounded-lg border border-destructive/20 bg-destructive/5 p-3 text-sm text-destructive"
                  >
                    <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
                    <span>{error}</span>
                  </div>
                )}

                <div className="space-y-2">
                  <label htmlFor="login-username" className="text-sm font-medium">
                    Username
                  </label>
                  <div className="relative">
                    <User className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                    <Input
                      id="login-username"
                      name="username"
                      autoComplete="username"
                      className="h-11 pl-10"
                      placeholder="Enter your username"
                      value={username}
                      onChange={(e) => setUsername(e.target.value)}
                      required
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <div className="flex items-center justify-between gap-3">
                    <label htmlFor="login-password" className="text-sm font-medium">
                      Password
                    </label>
                    {!isAdmin && (
                      <Link
                        to={isApp ? "/app/forgot-password" : "/forgot-password"}
                        className="text-xs font-medium text-primary hover:underline"
                      >
                        Forgot password?
                      </Link>
                    )}
                  </div>
                  <div className="relative">
                    <Lock className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                    <Input
                      id="login-password"
                      name="password"
                      type="password"
                      autoComplete="current-password"
                      className="h-11 pl-10"
                      placeholder="Enter your password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      required
                    />
                  </div>
                </div>
              </CardContent>

              <CardFooter className="flex-col gap-4 pt-2">
                <Button type="submit" disabled={loading} className="h-11 w-full">
                  {loading ? "Signing in..." : isAdmin ? "Continue securely" : "Sign in"}
                  {!loading && <ArrowRight className="ml-2 h-4 w-4" />}
                </Button>

                {!isAdmin && (
                  <p className="text-center text-sm text-muted-foreground">
                    New to CyberScout?{" "}
                    <Link
                      to={isApp ? "/app/register" : "/register"}
                      className="font-semibold text-primary hover:underline"
                    >
                      Create an account
                    </Link>
                  </p>
                )}
              </CardFooter>
            </form>
          </Card>

          {isAdmin && (
            <p className="mt-5 text-center text-xs text-muted-foreground">
              <Lock className="mr-1 inline h-3.5 w-3.5" />
              Administrative access is monitored and audited.
            </p>
          )}
        </div>
      </section>
    </main>
  )
}
