import { useEffect, useState } from "react"
import { Calendar, Play, Pause, RotateCw, RefreshCw, Clock, AlertCircle } from "lucide-react"
import { adminApi } from "@/lib/api"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { useToast } from "@/components/ui/toast"

export function AdminScheduler() {
  const { toast } = useToast()
  const [status, setStatus] = useState<Awaited<ReturnType<typeof adminApi.schedulerStatus>> | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [action, setAction] = useState<"run" | "pause" | "resume" | "restart" | null>(null)

  const loadStatus = async () => {
    setLoading(true)
    setLoadError(null)
    try {
      setStatus(await adminApi.schedulerStatus())
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : "Scheduler status could not be loaded.")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadStatus()
  }, [])

  const handleAction = async (action: "run" | "pause" | "resume" | "restart") => {
    setAction(action)
    try {
      if (action === "run") {
        await adminApi.triggerRun()
        toast({ title: "Triggered Run", description: "Scheduled pipeline triggered immediately.", variant: "success" })
      } else if (action === "pause") {
        await adminApi.schedulerPause()
        toast({ title: "Scheduler Paused", description: "Cron tasks paused.", variant: "default" })
      } else if (action === "resume") {
        await adminApi.schedulerResume()
        toast({ title: "Scheduler Resumed", description: "Cron tasks active.", variant: "success" })
      } else if (action === "restart") {
        await adminApi.schedulerRestart()
        toast({ title: "Scheduler Restarted", description: "Pipeline workers re-initialized.", variant: "success" })
      }
      await loadStatus()
    } catch (err: any) {
      toast({ title: "Action Failed", description: err.message || "Failed.", variant: "destructive" })
    } finally {
      setAction(null)
    }
  }

  const daemonRunning = status?.background_daemon?.running
  const reportSchedule = status?.report_schedule

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-cyber-blue">Operations</p>
          <h2 className="mt-1 text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <Calendar className="h-6 w-6 text-cyber-blue" /> Scheduler controls
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            Manage scheduled work and review the current runtime state.
          </p>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          <Button
            size="sm"
            onClick={() => handleAction("run")}
            disabled={loading || action !== null}
            className="bg-cyber-blue hover:bg-cyber-blue-light text-white"
          >
            <Play className="h-3.5 w-3.5 mr-1.5" /> {action === "run" ? "Starting..." : "Run now"}
          </Button>

          {daemonRunning === true ? (
            <Button
              variant="outline"
              size="sm"
              onClick={() => handleAction("pause")}
              disabled={loading || action !== null}
            >
              <Pause className="h-3.5 w-3.5 mr-1.5" /> {action === "pause" ? "Pausing..." : "Pause"}
            </Button>
          ) : daemonRunning === false ? (
            <Button
              variant="outline"
              size="sm"
              onClick={() => handleAction("resume")}
              disabled={loading || action !== null}
              className="text-emerald-700 border-emerald-500/30"
            >
              <Play className="h-3.5 w-3.5 mr-1.5" /> {action === "resume" ? "Resuming..." : "Resume"}
            </Button>
          ) : null}

          <Button
            variant="ghost"
            size="sm"
            onClick={() => handleAction("restart")}
            disabled={loading || action !== null}
          >
            <RotateCw className={`h-3.5 w-3.5 mr-1.5 ${action === "restart" ? "animate-spin" : ""}`} /> Restart
          </Button>
          <Button variant="outline" size="sm" onClick={loadStatus} disabled={loading || action !== null}>
            <RefreshCw className={`h-3.5 w-3.5 mr-1.5 ${loading ? "animate-spin" : ""}`} /> Refresh
          </Button>
        </div>
      </div>

      {loadError && (
        <div role="alert" className="flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{loadError}</span>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Background scheduler</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center gap-3">
              <span className={`h-2.5 w-2.5 rounded-full ${daemonRunning === true ? "bg-emerald-500" : daemonRunning === false ? "bg-amber-500" : "bg-muted-foreground"}`} />
              <p className="font-semibold text-foreground">
                {loading ? "Checking status…" : daemonRunning === true ? "Running" : daemonRunning === false ? "Paused" : "Status unavailable"}
              </p>
            </div>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div><p className="text-xs text-muted-foreground">Registered jobs</p><p className="mt-1 font-medium">{status?.background_daemon?.job_count ?? "—"}</p></div>
              <div><p className="text-xs text-muted-foreground">Schedule type</p><p className="mt-1 font-medium">{status?.background_daemon?.schedule_type ?? "—"}</p></div>
              <div><p className="text-xs text-muted-foreground">Interval</p><p className="mt-1 font-medium">{status?.background_daemon?.interval_seconds != null ? `${status.background_daemon.interval_seconds} seconds` : "—"}</p></div>
              <div><p className="text-xs text-muted-foreground">Pipeline scan</p><p className="mt-1 font-medium">{status?.scan_active === true ? "Active" : status?.scan_active === false ? "Idle" : "—"}</p></div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2"><Clock className="h-4 w-4 text-cyber-blue" /> Report schedule</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <div className="flex justify-between gap-4"><span className="text-muted-foreground">Delivery</span><span className="font-medium">{reportSchedule?.enabled ? "Enabled" : reportSchedule?.enabled === false ? "Disabled" : "—"}</span></div>
            <div className="flex justify-between gap-4"><span className="text-muted-foreground">Frequency</span><span className="font-medium">{reportSchedule?.frequency || "—"}</span></div>
            <div className="flex justify-between gap-4"><span className="text-muted-foreground">Next run</span><span className="text-right font-medium">{reportSchedule?.next_run || "—"}</span></div>
            <div className="flex justify-between gap-4"><span className="text-muted-foreground">Last pipeline run</span><span className="text-right font-medium">{reportSchedule?.last_pipeline_run || "—"}</span></div>
            <div className="flex justify-between gap-4"><span className="text-muted-foreground">Last email</span><span className="text-right font-medium">{reportSchedule?.last_email_sent || "—"}</span></div>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

