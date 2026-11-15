import { useEffect, useState } from "react"
import { User, Shield, Key, Bell, Check, AlertCircle } from "lucide-react"
import { useAuth } from "@/lib/auth-context"
import { authApi, notificationsApi, type NotificationPreferences } from "@/lib/api"
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

export function UserProfile() {
  const { user } = useAuth()
  const [currentPassword, setCurrentPassword] = useState("")
  const [newPassword, setNewPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [pwStatus, setPwStatus] = useState<{ type: "success" | "error" | null; message: string }>({
    type: null,
    message: "",
  })
  const [pwLoading, setPwLoading] = useState(false)

  const [notificationPrefs, setNotificationPrefs] = useState<NotificationPreferences | null>(null)
  const [prefsLoading, setPrefsLoading] = useState(true)
  const [prefsSaving, setPrefsSaving] = useState(false)
  const [prefsStatus, setPrefsStatus] = useState<{ type: "success" | "error" | null; message: string }>({
    type: null,
    message: "",
  })

  const loadNotificationPreferences = async () => {
    setPrefsLoading(true)
    setPrefsStatus({ type: null, message: "" })
    try {
      const res = await notificationsApi.preferences()
      setNotificationPrefs(res.preferences)
    } catch (err) {
      setPrefsStatus({
        type: "error",
        message: err instanceof Error ? err.message : "Notification preferences could not be loaded.",
      })
    } finally {
      setPrefsLoading(false)
    }
  }

  useEffect(() => {
    void loadNotificationPreferences()
  }, [])

  const handlePasswordChange = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!currentPassword || !newPassword) {
      setPwStatus({ type: "error", message: "Please fill in all password fields." })
      return
    }
    if (newPassword.length < 8) {
      setPwStatus({ type: "error", message: "New password must be at least 8 characters long." })
      return
    }
    if (newPassword !== confirmPassword) {
      setPwStatus({ type: "error", message: "New passwords do not match." })
      return
    }

    setPwLoading(true)
    setPwStatus({ type: null, message: "" })

    try {
      await authApi.changePassword({
        current_password: currentPassword,
        new_password: newPassword,
      })
      setPwStatus({ type: "success", message: "Password updated successfully!" })
      setCurrentPassword("")
      setNewPassword("")
      setConfirmPassword("")
    } catch (err: any) {
      setPwStatus({
        type: "error",
        message: err.message || "Failed to update password. Check your current password.",
      })
    } finally {
      setPwLoading(false)
    }
  }

  const handleSavePreferences = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!notificationPrefs) return

    setPrefsSaving(true)
    setPrefsStatus({ type: null, message: "" })
    try {
      const res = await notificationsApi.updatePreferences(notificationPrefs)
      if (res.status !== "success") throw new Error("Notification preferences were not saved.")
      setNotificationPrefs(res.preferences)
      setPrefsStatus({ type: "success", message: "Notification preferences saved." })
    } catch (err) {
      setPrefsStatus({
        type: "error",
        message: err instanceof Error ? err.message : "Notification preferences could not be saved.",
      })
    } finally {
      setPrefsSaving(false)
    }
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-cyber-blue">Your workspace</p>
        <h2 className="mt-1 text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
          <User className="h-6 w-6 text-cyber-blue" /> Account and security
        </h2>
        <p className="text-sm text-muted-foreground mt-1">
          Manage your personal details, credentials, and notification settings.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <Card className="md:col-span-1">
          <CardHeader>
            <CardTitle className="text-base">Profile details</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-col items-center text-center space-y-2 pb-4 border-b">
              <div className="h-16 w-16 rounded-full bg-cyber-blue/15 text-cyber-blue flex items-center justify-center font-bold text-2xl">
                {user?.username?.substring(0, 2).toUpperCase() || "US"}
              </div>
              <h3 className="font-semibold text-foreground">{user?.username}</h3>
              <span className="inline-flex items-center gap-1 rounded-full bg-muted px-2.5 py-0.5 text-xs font-mono font-medium text-muted-foreground">
                <Shield className="h-3 w-3" /> {user?.role || "Viewer"}
              </span>
            </div>

            <div className="space-y-2 text-xs">
              <div>
                <span className="text-muted-foreground block text-[11px]">Email Address</span>
                <span className="font-medium text-foreground">{user?.email || "Not specified"}</span>
              </div>
              <div>
                <span className="text-muted-foreground block text-[11px]">Admin Access</span>
                <span className="font-semibold text-foreground">
                  {user?.is_admin ? "Enabled (Administrator)" : "Standard User"}
                </span>
              </div>
            </div>
          </CardContent>
        </Card>

        <div className="md:col-span-2 space-y-6">
          <Card>
            <form onSubmit={handlePasswordChange}>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <Key className="h-4 w-4 text-cyber-blue" /> Change password
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {pwStatus.type === "success" && (
                  <div className="p-3 rounded-md bg-emerald-500/10 border border-emerald-500/30 text-emerald-700 dark:text-emerald-400 text-xs flex items-center gap-2">
                    <Check className="h-4 w-4 shrink-0" />
                    <span>{pwStatus.message}</span>
                  </div>
                )}
                {pwStatus.type === "error" && (
                  <div className="p-3 rounded-md bg-destructive/10 border border-destructive/30 text-destructive text-xs flex items-center gap-2">
                    <AlertCircle className="h-4 w-4 shrink-0" />
                    <span>{pwStatus.message}</span>
                  </div>
                )}

                <div className="space-y-1">
                  <label htmlFor="current-password" className="text-sm font-medium text-foreground">Current password</label>
                  <Input
                    id="current-password"
                    type="password"
                    autoComplete="current-password"
                    value={currentPassword}
                    onChange={(e) => setCurrentPassword(e.target.value)}
                    placeholder="Enter current password"
                    required
                  />
                </div>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <label htmlFor="new-password" className="text-sm font-medium text-foreground">New password</label>
                    <Input
                      id="new-password"
                      type="password"
                      autoComplete="new-password"
                      value={newPassword}
                      onChange={(e) => setNewPassword(e.target.value)}
                      placeholder="Min. 8 characters"
                      required
                    />
                  </div>
                  <div className="space-y-1">
                    <label htmlFor="confirm-password" className="text-sm font-medium text-foreground">Confirm new password</label>
                    <Input
                      id="confirm-password"
                      type="password"
                      autoComplete="new-password"
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      placeholder="Repeat new password"
                      required
                    />
                  </div>
                </div>
              </CardContent>
              <CardFooter className="border-t pt-3 flex justify-end">
                <Button
                  type="submit"
                  size="sm"
                  disabled={pwLoading}
                  className="bg-cyber-blue hover:bg-cyber-blue-light text-white text-xs"
                >
                  {pwLoading ? "Updating..." : "Update Password"}
                </Button>
              </CardFooter>
            </form>
          </Card>

          <Card>
            <form onSubmit={handleSavePreferences}>
              <CardHeader>
                <CardTitle className="text-base flex items-center gap-2">
                  <Bell className="h-4 w-4 text-cyber-blue" /> Notification preferences
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                {prefsStatus.type && (
                  <div
                    role={prefsStatus.type === "error" ? "alert" : "status"}
                    className={`p-3 rounded-md border text-sm flex items-center gap-2 ${
                      prefsStatus.type === "success"
                        ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-700"
                        : "bg-destructive/10 border-destructive/30 text-destructive"
                    }`}
                  >
                    {prefsStatus.type === "success" ? <Check className="h-4 w-4 shrink-0" /> : <AlertCircle className="h-4 w-4 shrink-0" />}
                    <span>{prefsStatus.message}</span>
                  </div>
                )}
                {prefsLoading ? (
                  <p className="text-sm text-muted-foreground">Loading saved preferences…</p>
                ) : notificationPrefs ? (
                  <>
                    <label className="flex items-center justify-between gap-4 p-3 rounded-lg border hover:bg-muted/30 cursor-pointer">
                      <span>
                        <span className="block text-sm font-medium text-foreground">Email notifications</span>
                        <span className="block text-xs text-muted-foreground mt-1">Allow notification delivery by email.</span>
                      </span>
                      <input
                        type="checkbox"
                        checked={notificationPrefs.email_notifications_enabled}
                        onChange={(e) => setNotificationPrefs((current) => current ? { ...current, email_notifications_enabled: e.target.checked } : current)}
                        className="rounded border-input text-primary focus:ring-ring"
                      />
                    </label>
                    <label className="flex items-center justify-between gap-4 p-3 rounded-lg border hover:bg-muted/30 cursor-pointer">
                      <span>
                        <span className="block text-sm font-medium text-foreground">In-app inbox alerts</span>
                        <span className="block text-xs text-muted-foreground mt-1">Show notifications in your account inbox.</span>
                      </span>
                      <input
                        type="checkbox"
                        checked={notificationPrefs.in_app_notifications_enabled}
                        onChange={(e) => setNotificationPrefs((current) => current ? { ...current, in_app_notifications_enabled: e.target.checked } : current)}
                        className="rounded border-input text-primary focus:ring-ring"
                      />
                    </label>
                    <label className="flex items-center justify-between gap-4 p-3 rounded-lg border hover:bg-muted/30 cursor-pointer">
                      <span>
                        <span className="block text-sm font-medium text-foreground">New opportunity alerts</span>
                        <span className="block text-xs text-muted-foreground mt-1">Notify me when new matching opportunities are found.</span>
                      </span>
                      <input
                        type="checkbox"
                        checked={notificationPrefs.notify_new_opportunities}
                        onChange={(e) => setNotificationPrefs((current) => current ? { ...current, notify_new_opportunities: e.target.checked } : current)}
                        className="rounded border-input text-primary focus:ring-ring"
                      />
                    </label>
                    <label className="flex items-center justify-between gap-4 p-3 rounded-lg border hover:bg-muted/30 cursor-pointer">
                      <span>
                        <span className="block text-sm font-medium text-foreground">Weekly digest</span>
                        <span className="block text-xs text-muted-foreground mt-1">Use weekly digest delivery instead of immediate delivery.</span>
                      </span>
                      <input
                        type="checkbox"
                        checked={notificationPrefs.delivery_mode === "digest" && notificationPrefs.digest_frequency === "weekly"}
                        onChange={(e) => setNotificationPrefs((current) => current ? {
                          ...current,
                          delivery_mode: e.target.checked ? "digest" : "immediate",
                          digest_frequency: e.target.checked ? "weekly" : current.digest_frequency,
                        } : current)}
                        className="rounded border-input text-primary focus:ring-ring"
                      />
                    </label>
                  </>
                ) : (
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-sm text-muted-foreground">Preferences are unavailable.</p>
                    <Button type="button" variant="outline" size="sm" onClick={() => void loadNotificationPreferences()}>
                      Try again
                    </Button>
                  </div>
                )}
              </CardContent>
              <CardFooter className="border-t pt-3 flex justify-end">
                <Button type="submit" size="sm" disabled={prefsLoading || prefsSaving || !notificationPrefs}>
                  {prefsSaving ? "Saving…" : "Save preferences"}
                </Button>
              </CardFooter>
            </form>
          </Card>
        </div>
      </div>
    </div>
  )
}

