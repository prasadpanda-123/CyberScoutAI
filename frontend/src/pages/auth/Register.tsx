import { useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import { AlertCircle, ArrowRight, CheckCircle2, Lock, Mail, Shield, User } from "lucide-react"
import { authApi } from "@/lib/api"
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

export function Register() {
  const navigate = useNavigate()
  const isApp = window.location.pathname.startsWith("/app")
  const [username, setUsername] = useState("")
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError(null)

    if (password !== confirmPassword) {
      setError("Passwords do not match.")
      return
    }

    if (password.length < 8) {
      setError("Password must be at least 8 characters long.")
      return
    }

    setLoading(true)
    try {
      await authApi.register({ username, email, password })
      navigate(isApp ? "/app/login?registered=true" : "/login?registered=true")
    } catch (err: any) {
      setError(err.message || "Registration failed. Try a different username or email.")
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
          <p className="text-xs font-bold uppercase tracking-[0.16em] text-cyan-300">
            Made for your next step
          </p>
          <h1 className="mt-5 text-4xl font-semibold leading-tight tracking-tight xl:text-5xl">
            Build your cybersecurity journey.
          </h1>
          <p className="mt-5 max-w-lg text-sm leading-7 text-slate-300 xl:text-base">
            Create a private account to discover opportunities, save promising listings, and
            revisit the details when you are ready.
          </p>
          <div className="mt-8 space-y-3">
            {[
              "Browse multiple opportunity types",
              "Keep a personal saved list",
              "See review details before applying",
            ].map((item) => (
              <p key={item} className="flex items-center gap-3 text-sm text-slate-200">
                <CheckCircle2 className="h-4 w-4 text-cyan-300" />
                {item}
              </p>
            ))}
          </div>
        </div>

        <p className="relative text-xs text-slate-400">
          Your account is for discovery and organization. Apply directly with each program.
        </p>
      </section>

      <section className="flex min-h-screen items-center justify-center px-4 py-10 sm:px-8">
        <div className="w-full max-w-[460px]">
          <Link to="/" className="mb-7 flex items-center justify-center gap-2 lg:hidden">
            <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary text-white">
              <Shield className="h-5 w-5" />
            </span>
            <span className="text-lg font-bold tracking-tight">
              CyberScout<span className="text-cyber-blue">.AI</span>
            </span>
          </Link>

          <div className="mb-6">
            <p className="text-xs font-bold uppercase tracking-[0.14em] text-primary">
              Get started
            </p>
            <h2 className="mt-2 text-3xl font-bold tracking-tight">Create your account</h2>
            <p className="mt-2 text-sm leading-6 text-muted-foreground">
              Set up your profile to organize the opportunities you want to explore.
            </p>
          </div>

          <Card className="border-border/80 shadow-[0_12px_40px_rgba(16,24,40,0.07)]">
            <CardHeader className="space-y-1 pb-4">
              <CardTitle className="text-base">Account details</CardTitle>
              <CardDescription>Use an email address you can access.</CardDescription>
            </CardHeader>

            <form onSubmit={handleSubmit}>
              <CardContent className="space-y-4">
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
                  <label htmlFor="register-username" className="text-sm font-medium">
                    Username
                  </label>
                  <div className="relative">
                    <User className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                    <Input
                      id="register-username"
                      name="username"
                      autoComplete="username"
                      className="h-11 pl-10"
                      placeholder="Choose a username"
                      value={username}
                      onChange={(e) => setUsername(e.target.value)}
                      required
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <label htmlFor="register-email" className="text-sm font-medium">
                    Email address
                  </label>
                  <div className="relative">
                    <Mail className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                    <Input
                      id="register-email"
                      name="email"
                      type="email"
                      autoComplete="email"
                      className="h-11 pl-10"
                      placeholder="you@example.com"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      required
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <label htmlFor="register-password" className="text-sm font-medium">
                    Password
                  </label>
                  <div className="relative">
                    <Lock className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                    <Input
                      id="register-password"
                      name="new-password"
                      type="password"
                      autoComplete="new-password"
                      className="h-11 pl-10"
                      placeholder="At least 8 characters"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      minLength={8}
                      required
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <label htmlFor="register-confirm-password" className="text-sm font-medium">
                    Confirm password
                  </label>
                  <div className="relative">
                    <Lock className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                    <Input
                      id="register-confirm-password"
                      name="confirm-password"
                      type="password"
                      autoComplete="new-password"
                      className="h-11 pl-10"
                      placeholder="Re-enter your password"
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      minLength={8}
                      required
                    />
                  </div>
                </div>
              </CardContent>

              <CardFooter className="flex-col gap-4 pt-2">
                <Button type="submit" disabled={loading} className="h-11 w-full">
                  {loading ? "Creating account..." : "Create account"}
                  {!loading && <ArrowRight className="ml-2 h-4 w-4" />}
                </Button>
                <p className="text-center text-sm text-muted-foreground">
                  Already have an account?{" "}
                  <Link
                    to={isApp ? "/app/login" : "/login"}
                    className="font-semibold text-primary hover:underline"
                  >
                    Sign in
                  </Link>
                </p>
              </CardFooter>
            </form>
          </Card>
        </div>
      </section>
    </main>
  )
}
