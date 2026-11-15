import { useState } from "react"
import { Link } from "react-router-dom"
import { Shield, Mail, ArrowRight, CheckCircle, AlertCircle } from "lucide-react"
import { authApi } from "@/lib/api"
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { ThemeToggle } from "@/components/ui/theme-toggle"

export function ForgotPassword() {
  const [email, setEmail] = useState("")
  const [loading, setLoading] = useState(false)
  const [submitted, setSubmitted] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError(null)

    try {
      await authApi.forgotPassword(email)
      setSubmitted(true)
    } catch (err: any) {
      setError(err.message || "Failed to dispatch password recovery email.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <main className="min-h-screen bg-background px-4 py-10 sm:px-8">
      <ThemeToggle className="fixed right-4 top-4 z-50" />
      <div className="mx-auto flex min-h-[calc(100vh-5rem)] w-full max-w-[440px] flex-col justify-center">
        <Link to="/" className="mb-8 flex items-center justify-center gap-2">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-sm">
            <Shield className="h-7 w-7" />
          </div>
          <span className="text-lg font-bold tracking-tight text-foreground">
            CyberScout<span className="text-cyber-blue">.AI</span>
          </span>
        </Link>

        <Card className="border-border/80 shadow-[0_12px_40px_rgba(0,0,0,0.32)]">
          <CardHeader className="space-y-1 pb-4">
            <CardTitle className="text-xl">Reset your password</CardTitle>
            <CardDescription>
              Enter your account email to receive a password recovery link.
            </CardDescription>
          </CardHeader>

          {submitted ? (
            <CardContent className="space-y-4 py-6 text-center">
              <CheckCircle className="mx-auto h-12 w-12 text-emerald-600" />
              <h4 className="text-base font-semibold text-foreground">Check your inbox</h4>
              <p className="text-sm leading-6 text-muted-foreground">
                If an account exists for that email, password reset instructions will be sent.
              </p>
              <Button asChild variant="outline" className="mt-2 w-full">
                <Link to={window.location.pathname.startsWith("/app") ? "/app/login" : "/login"}>Return to Login</Link>
              </Button>
            </CardContent>
          ) : (
            <form onSubmit={handleSubmit}>
              <CardContent className="space-y-3.5">
                {error && (
                  <div role="alert" className="flex items-center gap-2 rounded-lg border border-destructive/20 bg-destructive/5 p-3 text-sm text-destructive">
                    <AlertCircle className="h-4 w-4 shrink-0" />
                    <span>{error}</span>
                  </div>
                )}

                <div className="space-y-2">
                  <label htmlFor="recovery-email" className="text-sm font-medium">Account email</label>
                  <div className="relative">
                    <Mail className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
                    <Input
                      id="recovery-email"
                      name="email"
                      type="email"
                      autoComplete="email"
                      className="h-11 pl-10"
                      placeholder="user@example.com"
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      required
                    />
                  </div>
                </div>
              </CardContent>

              <CardFooter className="flex flex-col gap-4 pt-2">
                <Button
                  type="submit"
                  disabled={loading}
                  className="h-11 w-full"
                >
                  {loading ? "Sending link..." : "Send reset link"}
                  {!loading && <ArrowRight className="ml-2 h-4 w-4" />}
                </Button>

                <p className="text-center text-sm text-muted-foreground">
                  Remembered your password?{" "}
                  <Link
                    to={window.location.pathname.startsWith("/app") ? "/app/login" : "/login"}
                    className="font-semibold text-primary hover:underline"
                  >
                    Back to login
                  </Link>
                </p>
              </CardFooter>
            </form>
          )}
        </Card>
      </div>
    </main>
  )
}

