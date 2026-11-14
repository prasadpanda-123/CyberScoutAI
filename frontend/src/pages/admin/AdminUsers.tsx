import { useEffect, useState } from "react"
import { Users, UserPlus, Lock, Unlock, Trash2, ShieldAlert, Check } from "lucide-react"
import { adminApi } from "@/lib/api"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/components/ui/dialog"
import { useToast } from "@/components/ui/toast"
import { Skeleton } from "@/components/ui/skeleton"

export function AdminUsers() {
  const { toast } = useToast()
  const [users, setUsers] = useState<any[]>([])
  const [admins, setAdmins] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)

  // Create User Modal state
  const [modalOpen, setModalOpen] = useState(false)
  const [newUsername, setNewUsername] = useState("")
  const [newEmail, setNewEmail] = useState("")
  const [newPassword, setNewPassword] = useState("")
  const [newRole, setNewRole] = useState("Viewer")
  const [creating, setCreating] = useState(false)

  const loadAccounts = async () => {
    setLoading(true)
    setLoadError(null)
    try {
      const res = await adminApi.users()
      if (res) {
        setUsers(res.users || [])
        setAdmins(res.admins || [])
      }
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : "Account data could not be loaded.")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadAccounts()
  }, [])

  const handleToggleUser = async (userId: string, currentActive: boolean) => {
    try {
      const result = await adminApi.toggleUser(userId)
      setUsers((prev) =>
        prev.map((u) => (u.id === userId ? { ...u, is_active: result.is_active ?? !currentActive } : u))
      )
      toast({
        title: "Account Status Updated",
        description: `Account has been ${!currentActive ? "unlocked" : "locked"}.`,
        variant: "success",
      })
    } catch (err: any) {
      toast({
        title: "Action Failed",
        description: err.message || "Failed to update account.",
        variant: "destructive",
      })
    }
  }

  const handleDeleteUser = async (userId: string) => {
    if (!window.confirm("Are you sure you want to permanently delete this user?")) return
    try {
      await adminApi.deleteUser(userId)
      setUsers((prev) => prev.filter((u) => u.id !== userId))
      toast({
        title: "User Deleted",
        description: "User account was removed.",
        variant: "default",
      })
    } catch (err: any) {
      toast({
        title: "Deletion Failed",
        description: err.message || "Failed to delete user.",
        variant: "destructive",
      })
    }
  }

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newUsername || !newPassword || newPassword.length < 8) {
      toast({
        title: "Validation Error",
        description: "Password must be at least 8 characters.",
        variant: "destructive",
      })
      return
    }

    setCreating(true)
    try {
      await adminApi.createUser({
        username: newUsername,
        email: newEmail,
        password: newPassword,
        role: newRole,
      })
      toast({
        title: "User Created",
        description: `User account "${newUsername}" successfully provisioned.`,
        variant: "success",
      })
      setModalOpen(false)
      setNewUsername("")
      setNewEmail("")
      setNewPassword("")
      await loadAccounts()
    } catch (err: any) {
      toast({
        title: "Creation Failed",
        description: err.message || "Failed to create user.",
        variant: "destructive",
      })
    } finally {
      setCreating(false)
    }
  }

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-cyber-blue">Administration</p>
          <h2 className="mt-1 text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <Users className="h-6 w-6 text-cyber-blue" /> User and role management
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            Manage registered accounts and review administrator records.
          </p>
        </div>

        <Button
          size="sm"
          onClick={() => setModalOpen(true)}
          className="bg-cyber-blue hover:bg-cyber-blue-light text-white"
        >
          <UserPlus className="h-3.5 w-3.5 mr-1.5" /> Provision New User
        </Button>
      </div>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base font-semibold flex items-center gap-2">
            <ShieldAlert className="h-4 w-4 text-cyber-blue" /> Administrator accounts
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead className="bg-muted/50 text-muted-foreground font-semibold uppercase text-[10px] tracking-wider border-b">
                <tr>
                  <th className="p-3">Username</th>
                  <th className="p-3">Role</th>
                  <th className="p-3">MFA status</th>
                  <th className="p-3 text-right">Access level</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {loading ? (
                  <tr><td colSpan={4} className="p-4"><Skeleton className="h-4 w-full" /></td></tr>
                ) : loadError ? (
                  <tr><td colSpan={4} className="p-5 text-sm text-destructive">Administrator records are unavailable.</td></tr>
                ) : admins.length === 0 ? (
                  <tr>
                    <td colSpan={4} className="p-5 text-sm text-muted-foreground">
                      No administrator records were returned.
                    </td>
                  </tr>
                ) : (
                  admins.map((adm, i) => (
                    <tr key={i} className="hover:bg-muted/20">
                      <td className="p-3 font-semibold text-foreground">
                        <span className="inline-flex items-center gap-2">
                        <span className="h-6 w-6 rounded-full bg-cyber-blue/15 text-cyber-blue flex items-center justify-center font-bold text-[10px]">
                          {adm.username?.substring(0, 2).toUpperCase() || "AD"}
                        </span>
                        {adm.username || "Unknown"}
                        </span>
                      </td>
                      <td className="p-3">{adm.role || "—"}</td>
                      <td className="p-3">
                        <span className={`inline-flex items-center gap-1 rounded px-2 py-0.5 text-[10px] font-semibold ${
                          adm.mfa_enabled === true ? "bg-emerald-500/10 text-emerald-700" :
                            adm.mfa_enabled === false ? "bg-amber-500/10 text-amber-700" : "bg-muted text-muted-foreground"
                        }`}>
                          {adm.mfa_enabled === true && <Check className="h-3 w-3" />}
                          {adm.mfa_enabled === true ? "Enabled" : adm.mfa_enabled === false ? "Disabled" : "Not reported"}
                        </span>
                      </td>
                      <td className="p-3 text-right font-medium text-foreground">
                        {adm.access_level || adm.role || "—"}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="text-base font-semibold flex items-center gap-2">
            <Users className="h-4 w-4 text-cyber-blue" /> Registered Users
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead className="bg-muted/50 text-muted-foreground font-semibold uppercase text-[10px] tracking-wider border-b">
                <tr>
                  <th className="p-3">Username</th>
                  <th className="p-3">Email Address</th>
                  <th className="p-3">Assigned Role</th>
                  <th className="p-3">Status</th>
                  <th className="p-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {loading ? (
                  Array.from({ length: 3 }).map((_, i) => (
                    <tr key={i}>
                      <td colSpan={5} className="p-4">
                        <Skeleton className="h-4 w-full" />
                      </td>
                    </tr>
                  ))
                ) : loadError ? (
                  <tr><td colSpan={5} className="p-5 text-sm text-destructive">User records are unavailable.</td></tr>
                ) : users.length === 0 ? (
                  <tr>
                    <td colSpan={5} className="p-8 text-center text-muted-foreground">
                      No standard user accounts registered.
                    </td>
                  </tr>
                ) : (
                  users.map((u) => (
                    <tr key={u.id} className="hover:bg-muted/20 transition-colors">
                      <td className="p-3 font-semibold text-foreground">{u.username}</td>
                      <td className="p-3 text-muted-foreground">{u.email || "N/A"}</td>
                      <td className="p-3 font-mono">{u.role || "Viewer"}</td>
                      <td className="p-3">
                        <span
                          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold ${
                            u.is_active !== false
                              ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                              : "bg-destructive/10 text-destructive"
                          }`}
                        >
                          {u.is_active !== false ? "Active" : "Locked"}
                        </span>
                      </td>
                      <td className="p-3 text-right">
                        <div className="inline-flex items-center gap-1.5">
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => handleToggleUser(u.id, u.is_active !== false)}
                            className="h-7 w-7 text-muted-foreground hover:text-foreground"
                            title={u.is_active !== false ? "Lock Account" : "Unlock Account"}
                          >
                            {u.is_active !== false ? <Lock className="h-3.5 w-3.5" /> : <Unlock className="h-3.5 w-3.5" />}
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => handleDeleteUser(u.id)}
                            className="h-7 w-7 text-muted-foreground hover:text-destructive"
                            title="Delete User"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>

      <Dialog open={modalOpen} onOpenChange={setModalOpen}>
        <DialogContent>
          <form onSubmit={handleCreateUser}>
            <DialogHeader>
              <DialogTitle>Provision New User</DialogTitle>
            </DialogHeader>
            <div className="space-y-3 py-4 text-xs">
              <div className="space-y-1">
                <label htmlFor="new-username" className="font-medium text-foreground">Username</label>
                <Input
                  id="new-username"
                  value={newUsername}
                  onChange={(e) => setNewUsername(e.target.value)}
                  placeholder="e.g. cyber_analyst"
                  required
                />
              </div>

              <div className="space-y-1">
                <label htmlFor="new-email" className="font-medium text-foreground">Email address</label>
                <Input
                  id="new-email"
                  type="email"
                  value={newEmail}
                  onChange={(e) => setNewEmail(e.target.value)}
                  placeholder="user@example.com"
                  required
                />
              </div>

              <div className="space-y-1">
                <label htmlFor="new-password" className="font-medium text-foreground">Password (minimum 8 characters)</label>
                <Input
                  id="new-password"
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="Strong initial password"
                  required
                />
              </div>

              <div className="space-y-1">
                <label htmlFor="new-role" className="font-medium text-foreground">Assigned role</label>
                <select
                  id="new-role"
                  value={newRole}
                  onChange={(e) => setNewRole(e.target.value)}
                  className="w-full bg-background border rounded-md px-3 py-1.5 text-xs text-foreground focus:outline-none"
                >
                  <option value="Viewer">Viewer (Read-only catalog & bookmarks)</option>
                  <option value="Operator">Operator (Trigger manual collector runs)</option>
                  <option value="User">User (Standard researcher)</option>
                </select>
              </div>
            </div>
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setModalOpen(false)}
                className="text-xs"
              >
                Cancel
              </Button>
              <Button
                type="submit"
                size="sm"
                disabled={creating}
                className="bg-cyber-blue hover:bg-cyber-blue-light text-white text-xs"
              >
                {creating ? "Provisioning..." : "Provision Account"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}

