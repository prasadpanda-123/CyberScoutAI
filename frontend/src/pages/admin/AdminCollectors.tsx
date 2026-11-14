import { useEffect, useState } from "react"
import { Cpu, Play, CheckCircle2, AlertCircle, RefreshCw } from "lucide-react"
import { adminApi, type AdminSourceHealthRecord } from "@/lib/api"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { useToast } from "@/components/ui/toast"

export function AdminCollectors() {
  const { toast } = useToast()
  const [sources, setSources] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const loadSources = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await adminApi.sourceHealth()
      const definitions = res.sources
      const records = res.records
      const recordsById = new Map<string, AdminSourceHealthRecord>(
        records.map((record) => [String(record.source_id ?? "").toLowerCase(), record])
      )
      const matchedIds = new Set<string>()
      const configuredSources = definitions.map((source) => {
        const sourceId = String(source.id ?? "").toLowerCase()
        const sourceName = String(source.name ?? "").toLowerCase()
        const record = recordsById.get(sourceId) ?? recordsById.get(sourceName)
        if (record) matchedIds.add(String(record.source_id ?? "").toLowerCase())
        return {
          ...source,
          ...(record ?? {}),
          display_name: source.name ?? record?.source_id ?? "Source",
          status: record?.health_status ?? "UNKNOWN",
          items_discovered: record?.items_seen,
          last_checked: record?.last_attempt,
        }
      })
      const unlistedRecords = records
        .filter((record) => !matchedIds.has(String(record.source_id ?? "").toLowerCase()))
        .map((record) => ({
          ...record,
          display_name: record.source_id || "Source",
          status: record.health_status ?? "UNKNOWN",
          items_discovered: record.items_seen,
          last_checked: record.last_attempt,
        }))
      setSources([...configuredSources, ...unlistedRecords])
    } catch (err) {
      setError(err instanceof Error ? err.message : "Source telemetry could not be loaded.")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadSources()
  }, [])

  const handleRunCollector = async () => {
    setRunning(true)
    try {
      await adminApi.triggerRun()
      toast({
        title: "Collector Job Queued",
        description: "A collection run was requested.",
        variant: "success",
      })
      window.setTimeout(() => { void loadSources() }, 2000)
    } catch (err: any) {
      toast({
        title: "Failed to Run",
        description: err.message || "Collector trigger failed.",
        variant: "destructive",
      })
    } finally {
      setRunning(false)
    }
  }

  const healthyCount = sources.filter((source) => String(source.status).toUpperCase() === "HEALTHY").length
  const attentionCount = sources.filter((source) => ["DEGRADED", "STALE", "FAILED"].includes(String(source.status).toUpperCase())).length
  const unverifiedCount = sources.filter((source) => !["HEALTHY", "DEGRADED", "STALE", "FAILED"].includes(String(source.status).toUpperCase())).length

  const statusLabel = (status: string) => {
    const normalized = status.toUpperCase()
    if (normalized === "HEALTHY") return "Healthy"
    if (normalized === "DEGRADED") return "Degraded"
    if (normalized === "STALE") return "Stale"
    if (normalized === "FAILED") return "Failed"
    return "No telemetry"
  }

  const statusClass = (status: string) => {
    const normalized = status.toUpperCase()
    if (normalized === "HEALTHY") return "bg-emerald-500/10 text-emerald-700"
    if (normalized === "DEGRADED" || normalized === "STALE") return "bg-amber-500/10 text-amber-700"
    if (normalized === "FAILED") return "bg-destructive/10 text-destructive"
    return "bg-muted text-muted-foreground"
  }

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-cyber-blue">Operations</p>
          <h2 className="mt-1 text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <Cpu className="h-6 w-6 text-cyber-blue" /> Collector health
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            Provider health is based on persisted checks; unverified integrations are not reported as healthy.
          </p>
        </div>

        <div className="flex items-center gap-2.5">
          <Button
            size="sm"
            onClick={handleRunCollector}
            disabled={running || loading}
            className="bg-cyber-blue hover:bg-cyber-blue-light text-white"
          >
            <Play className="h-3.5 w-3.5 mr-1.5" />
            {running ? "Starting..." : "Run Manual Collection"}
          </Button>
          <Button variant="outline" size="sm" onClick={loadSources} disabled={loading}>
            <RefreshCw className={`h-3.5 w-3.5 mr-1.5 ${loading ? "animate-spin" : ""}`} /> Refresh
          </Button>
        </div>
      </div>

      {error && (
        <div role="alert" className="flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <Card><CardContent className="pt-5"><p className="text-xs text-muted-foreground">Healthy checks</p><p className="mt-1 text-2xl font-semibold text-emerald-700">{loading ? "—" : healthyCount}</p></CardContent></Card>
        <Card><CardContent className="pt-5"><p className="text-xs text-muted-foreground">Needs attention</p><p className="mt-1 text-2xl font-semibold text-amber-700">{loading ? "—" : attentionCount}</p></CardContent></Card>
        <Card><CardContent className="pt-5"><p className="text-xs text-muted-foreground">Unverified</p><p className="mt-1 text-2xl font-semibold text-foreground">{loading ? "—" : unverifiedCount}</p></CardContent></Card>
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base font-semibold">Configured sources</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead className="bg-muted/50 text-muted-foreground font-semibold uppercase text-[10px] tracking-wider border-b">
                <tr>
                  <th className="p-3">Source</th>
                  <th className="p-3">Type</th>
                  <th className="p-3">Status</th>
                  <th className="p-3">Items Seen</th>
                  <th className="p-3 text-right">Last Attempt</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {loading ? (
                  Array.from({ length: 4 }).map((_, i) => (
                    <tr key={i}>
                      <td colSpan={5} className="p-4">
                        <Skeleton className="h-4 w-full" />
                      </td>
                    </tr>
                  ))
                ) : error ? (
                  <tr><td colSpan={5} className="p-8 text-center text-muted-foreground">Source telemetry is unavailable.</td></tr>
                ) : sources.length === 0 ? (
                  <tr><td colSpan={5} className="p-8 text-center text-muted-foreground">No configured sources or health records were returned.</td></tr>
                ) : (
                  sources.map((src, idx) => (
                    <tr key={idx} className="hover:bg-muted/20 transition-colors">
                      <td className="p-3 font-semibold text-foreground">{src.display_name}</td>
                      <td className="p-3 text-muted-foreground">{src.type || "—"}</td>
                      <td className="p-3">
                        <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-semibold ${statusClass(String(src.status))}`}>
                          {String(src.status).toUpperCase() === "HEALTHY" && <CheckCircle2 className="h-3 w-3" />}
                          {statusLabel(String(src.status))}
                        </span>
                      </td>
                      <td className="p-3 font-mono text-foreground font-medium">
                        {src.items_discovered ?? "—"}
                      </td>
                      <td className="p-3 text-right text-muted-foreground font-mono">
                        {src.last_checked && !Number.isNaN(Date.parse(src.last_checked)) ? new Date(src.last_checked).toLocaleString() : "—"}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}

