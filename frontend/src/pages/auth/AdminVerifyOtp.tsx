import { useState, useEffect } from "react"
import { useNavigate, Link } from "react-router-dom"
import { ShieldCheck, ArrowRight, AlertCircle, Clock } from "lucide-react"
import { authApi } from "@/lib/api"
import { useAuth } from "@/lib/auth-context"
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

export function AdminVerifyOtp() {
  const navigate = useNavigate()
  const { refresh } = useAuth()
  const [otp, setOtp] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [countdown, setCountdown] = useState(300) // 5 minutes

  useEffect(() => {
    if (countdown <= 0) return
    const timer = setInterval(() => setCountdown((c) => c - 1), 1000)
    return () => clearInterval(timer)
  }, [countdown])

  const formatCountdown = () => {
    const min = Math.floor(countdown / 60)
    const sec = countdown % 60
    return `${min}:${sec < 10 ? "0" : ""}${sec}`
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (otp.length < 6) {
      setError("Please enter the complete 6-digit code.")
      return
    }

    setLoading(true)
    setError(null)
    try {
      await authApi.adminVerifyOtp(otp)
      await refresh()
      navigate(window.location.pathname.startsWith("/app") ? "/app/admin/dashboard" : "/admin/dashboard")
    } catch (err: any) {
      setError(err.message || "Invalid or expired OTP. Please try again.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-muted/20 flex flex-col justify-center items-center p-4">
      <div className="w-full max-w-md space-y-6">
        <div className="text-center space-y-2">
          <div className="h-12 w-12 rounded-xl bg-cyber-blue text-white flex items-center justify-center font-bold mx-auto shadow-md">
            <ShieldCheck className="h-7 w-7" />
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-foreground">
            Verify your sign-in
          </h1>
          <p className="text-sm text-muted-foreground">
            Enter the one-time code sent to your administrator email.
          </p>
        </div>

        <Card className="shadow-sm">
          <CardHeader className="space-y-1 pb-4">
            <CardTitle className="text-base font-bold">Two-step verification</CardTitle>
            <CardDescription className="text-sm">
              This additional step helps protect administrator access.
            </CardDescription>
          </CardHeader>

          <form onSubmit={handleSubmit}>
            <CardContent className="space-y-4">
              {error && (
                <div className="p-3 rounded-md bg-destructive/10 border border-destructive/30 text-destructive text-xs flex items-center gap-2">
                  <AlertCircle className="h-4 w-4 shrink-0" />
                  <span>{error}</span>
                </div>
              )}

              <div className="space-y-2">
                <label htmlFor="admin-otp" className="text-sm font-medium text-foreground block">
                  Verification code
                </label>
                <Input
                  id="admin-otp"
                  type="text"
                  maxLength={6}
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  pattern="[0-9]{6}"
                  aria-describedby="otp-expiry"
                  value={otp}
                  onChange={(e) => setOtp(e.target.value.replace(/\D/g, ""))}
                  placeholder="Enter 6-digit code"
                  className="font-mono text-lg tracking-[0.2em] h-12"
                  autoFocus
                  required
                />
              </div>

              <div id="otp-expiry" className="flex items-center gap-2 text-xs text-muted-foreground pt-1">
                <Clock className="h-3.5 w-3.5" />
                <span>{countdown > 0 ? `Code expiry window: ${formatCountdown()}` : "The code may have expired. Return to sign in to request another."}</span>
              </div>
            </CardContent>

            <CardFooter className="flex flex-col space-y-3 pt-2">
              <Button
                type="submit"
                disabled={loading || otp.length !== 6}
                className="w-full bg-cyber-blue hover:bg-cyber-blue-light text-white font-semibold shadow-sm"
              >
                {loading ? "Verifying…" : "Verify and continue"}
                <ArrowRight className="ml-2 h-3.5 w-3.5" />
              </Button>

              <div className="flex items-center justify-center w-full text-sm text-muted-foreground pt-2">
                <Link to="/app/login" className="hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded">
                  Back to Login
                </Link>
              </div>
            </CardFooter>
          </form>
        </Card>
      </div>
    </div>
  )
}

