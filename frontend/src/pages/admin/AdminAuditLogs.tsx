import { useEffect, useState } from "react"
import { FileText, Download, Search, RefreshCw, AlertCircle } from "lucide-react"
import { adminApi } from "@/lib/api"
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"

export function AdminAuditLogs() {
  const [logs, setLogs] = useState<any[]>([])
  const [search, setSearch] = useState("")
  const [outcomeFilter, setOutcomeFilter] = useState("ALL")
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadLogs = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await adminApi.auditLogs({ limit: 50 })
      setLogs(Array.isArray(res?.logs) ? res.logs : Array.isArray(res?.audit_logs) ? res.audit_logs : [])
    } catch (err) {
      setError(err instanceof Error ? err.message : "Audit logs could not be loaded.")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadLogs()
  }, [])

  const filteredLogs = logs.filter((log) => {
    if (outcomeFilter !== "ALL" && String(log.status || "").toUpperCase() !== outcomeFilter) return false
    if (!search) return true
    const q = search.toLowerCase()
    return (
      log.action?.toLowerCase().includes(q) ||
      log.event_type?.toLowerCase().includes(q) ||
      log.username?.toLowerCase().includes(q) ||
      log.source_ip?.toLowerCase().includes(q) ||
      log.details?.toLowerCase().includes(q)
    )
  })

  const exportJson = () => {
    const blob = new Blob([JSON.stringify(logs, null, 2)], { type: "application/json" })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement("a")
    anchor.href = url
    anchor.download = `cyberscout-audit-logs-${new Date().toISOString().slice(0, 10)}.json`
    anchor.click()
    window.setTimeout(() => URL.revokeObjectURL(url), 0)
  }

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-cyber-blue">Governance</p>
          <h2 className="mt-1 text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <FileText className="h-6 w-6 text-cyber-blue" /> Security audit logs
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            Review recorded authentication, administrative, and pipeline events.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={exportJson} disabled={logs.length === 0 || loading}>
            <Download className="h-3.5 w-3.5 mr-1.5" /> Export
          </Button>
          <Button variant="outline" size="sm" onClick={loadLogs} disabled={loading}>
            <RefreshCw className={`h-3.5 w-3.5 mr-1.5 ${loading ? "animate-spin" : ""}`} /> Refresh
          </Button>
        </div>
      </div>

      <div className="flex flex-col sm:flex-row gap-3 items-stretch sm:items-center justify-between">
        <div className="relative flex-1 max-w-sm">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search action, username, IP..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9 bg-card text-xs"
          />
        </div>

        <div className="flex items-center gap-2 text-xs">
          <label htmlFor="audit-outcome" className="text-muted-foreground">Outcome</label>
          <select
            id="audit-outcome"
            value={outcomeFilter}
            onChange={(e) => setOutcomeFilter(e.target.value)}
            className="bg-card border rounded-md px-2.5 py-1.5 text-foreground text-xs focus:outline-none"
          >
            <option value="ALL">All Outcomes</option>
            <option value="SUCCESS">SUCCESS</option>
            <option value="FLAGGED">FLAGGED</option>
            <option value="FAILED">FAILED</option>
          </select>
        </div>
      </div>

      {error && (
        <div role="alert" className="flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      <Card>
        <CardContent className="pt-6">
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead className="bg-muted/50 text-muted-foreground font-semibold uppercase text-[10px] tracking-wider border-b">
                <tr>
                  <th className="p-3">Timestamp</th>
                  <th className="p-3">Event type</th>
                  <th className="p-3">Activity</th>
                  <th className="p-3">Outcome</th>
                  <th className="p-3">Identity</th>
                  <th className="p-3 text-right">Source IP</th>
                </tr>
              </thead>
              <tbody className="divide-y font-mono">
                {loading ? (
                  Array.from({ length: 4 }).map((_, i) => (
                    <tr key={i}>
                      <td colSpan={6} className="p-4">
                        <Skeleton className="h-4 w-full" />
                      </td>
                    </tr>
                  ))
                ) : error ? (
                  <tr>
                    <td colSpan={6} className="p-8 text-center text-muted-foreground font-sans">
                      Audit events are unavailable. Refresh to try again.
                    </td>
                  </tr>
                ) : filteredLogs.length === 0 ? (
                  <tr>
                    <td colSpan={6} className="p-8 text-center text-muted-foreground font-sans">
                      No matching audit logs found.
                    </td>
                  </tr>
                ) : (
                  filteredLogs.map((log, idx) => (
                    <tr key={log.id || idx} className="hover:bg-muted/20 transition-colors">
                      <td className="p-3 text-muted-foreground whitespace-nowrap">
                        {(log.timestamp || log.created_at) && !Number.isNaN(Date.parse(log.timestamp || log.created_at)) ? new Date(log.timestamp || log.created_at).toLocaleString() : "—"}
                      </td>
                      <td className="p-3 font-semibold text-foreground">{log.event_type || "—"}</td>
                      <td className="p-3 text-muted-foreground font-sans">
                        <span className="font-medium text-foreground">{log.action || "—"}</span>
                        {log.details && <span className="block mt-1 text-[11px]">{log.details}</span>}
                      </td>
                      <td className="p-3">
                        <span
                          className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-[10px] font-semibold ${
                            String(log.status).toUpperCase() === "SUCCESS"
                              ? "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                              : String(log.status).toUpperCase() === "FLAGGED"
                              ? "bg-amber-500/10 text-amber-600 dark:text-amber-400"
                              : "bg-destructive/10 text-destructive"
                          }`}
                        >
                          {log.status || "UNKNOWN"}
                        </span>
                      </td>
                      <td className="p-3 text-foreground font-semibold">{log.username || log.user_id || "System"}</td>
                      <td className="p-3 text-right text-muted-foreground">{log.source_ip || "—"}</td>
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

