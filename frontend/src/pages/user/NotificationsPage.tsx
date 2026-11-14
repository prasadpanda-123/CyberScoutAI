import { useEffect, useState } from "react"
import { Link } from "react-router-dom"
import { Bell, CheckCheck, Clock, AlertCircle } from "lucide-react"
import { notificationsApi } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { EmptyState } from "@/components/ui/empty-state"
import { Skeleton } from "@/components/ui/skeleton"
import { useToast } from "@/components/ui/toast"

export function NotificationsPage() {
  const { toast } = useToast()
  const [notifications, setNotifications] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [markingIds, setMarkingIds] = useState<string[]>([])
  const [markingAll, setMarkingAll] = useState(false)

  const loadNotifications = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await notificationsApi.list()
      setNotifications(Array.isArray(res?.notifications) ? res.notifications : [])
    } catch (err) {
      setError(err instanceof Error ? err.message : "Notifications could not be loaded.")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadNotifications()
  }, [])

  const handleMarkRead = async (id: string) => {
    setMarkingIds((prev) => [...prev, id])
    try {
      const result = await notificationsApi.markRead(id)
      if (result?.status !== "success") throw new Error("This notification could not be updated.")
      setNotifications((prev) =>
        prev.map((n) => (n.id === id ? { ...n, is_read: true } : n))
      )
      toast({ title: "Marked as read", variant: "success" })
    } catch (err) {
      toast({
        title: "Update failed",
        description: err instanceof Error ? err.message : "The notification could not be updated.",
        variant: "destructive",
      })
    } finally {
      setMarkingIds((prev) => prev.filter((itemId) => itemId !== id))
    }
  }

  const handleMarkAllRead = async () => {
    setMarkingAll(true)
    try {
      const result = await notificationsApi.markAllRead()
      if (result?.status !== "success") throw new Error("Notifications could not be updated.")
      setNotifications((prev) => prev.map((n) => ({ ...n, is_read: true })))
      toast({ title: "Inbox cleared", description: "All notifications are marked as read.", variant: "success" })
    } catch (err) {
      toast({
        title: "Update failed",
        description: err instanceof Error ? err.message : "Notifications could not be updated.",
        variant: "destructive",
      })
    } finally {
      setMarkingAll(false)
    }
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-cyber-blue">Your workspace</p>
          <h2 className="mt-1 text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <Bell className="h-6 w-6 text-cyber-blue" /> Notifications
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            Updates and reminders related to your opportunity feed.
          </p>
        </div>

        {notifications.some((n) => !n.is_read) && (
          <Button
            variant="outline"
            size="sm"
            onClick={handleMarkAllRead}
            disabled={markingAll}
          >
            <CheckCheck className="h-3.5 w-3.5 mr-1.5" /> {markingAll ? "Updating…" : "Mark all as read"}
          </Button>
        )}
      </div>

      {error && (
        <div role="alert" className="flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
          <Button variant="outline" size="sm" className="ml-auto" onClick={loadNotifications}>Retry</Button>
        </div>
      )}

      {loading ? (
        <div className="space-y-3">
          {[1, 2, 3].map((i) => (
            <Card key={i} className="p-5 space-y-3">
              <Skeleton className="h-4 w-1/2" />
              <Skeleton className="h-3 w-4/5" />
            </Card>
          ))}
        </div>
      ) : error ? null : notifications.length === 0 ? (
        <EmptyState
          icon={Bell}
          title="You're all caught up"
          description="New updates will appear here when they are available."
        />
      ) : (
        <div className="space-y-3">
          {notifications.map((n) => (
            <Card
              key={n.id}
              className={`p-5 transition-colors ${
                !n.is_read
                  ? "border-cyber-blue/30 bg-card"
                  : "bg-muted/20"
              }`}
            >
              <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
                <div className="min-w-0 flex-1 space-y-2">
                <div className="flex items-center gap-2">
                  {n.opportunity_id ? (
                    <Link to={`/app/opportunities/${n.opportunity_id}`} className="text-sm font-semibold text-foreground hover:text-cyber-blue focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring rounded">
                      {n.title || "Opportunity update"}
                    </Link>
                  ) : (
                    <h4 className="text-sm font-semibold text-foreground">{n.title || "Notification"}</h4>
                  )}
                  {!n.is_read && (
                    <span className="h-2 w-2 rounded-full bg-cyber-blue shrink-0" aria-label="Unread" />
                  )}
                </div>
                <p className="text-xs leading-relaxed text-muted-foreground">
                  {n.message || "No additional details."}
                </p>
                <div className="flex items-center gap-2 pt-1 text-[11px] text-muted-foreground font-mono">
                  <Clock className="h-3 w-3" />
                  <span>
                    {n.created_at && !Number.isNaN(Date.parse(n.created_at))
                      ? new Date(n.created_at).toLocaleString()
                      : "Time unavailable"}
                  </span>
                </div>
              </div>

              {!n.is_read && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => void handleMarkRead(n.id)}
                  disabled={markingIds.includes(n.id)}
                  className="shrink-0 text-xs"
                >
                  {markingIds.includes(n.id) ? "Saving…" : "Mark read"}
                </Button>
              )}
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}

