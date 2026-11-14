import { useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"
import {
  Cpu,
  AlertTriangle,
  Play,
  RotateCw,
  Database,
  ArrowRight,
  Activity,
  Layers,
  ShieldCheck,
  Users,
  CheckCircle2,
  Gauge,
} from "lucide-react"
import { adminApi, type AdminDashboardStats, type AdminDailyApiBudget } from "@/lib/api"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { useToast } from "@/components/ui/toast"

const pipelineStages = [
  { name: "Discovery", desc: "Source collection" },
  { name: "Extraction", desc: "Content parsing" },
  { name: "Classification", desc: "Opportunity analysis" },
  { name: "Cost review", desc: "Free-only verification" },
  { name: "Deduplication", desc: "Identity and ranking" },
  { name: "Promotion", desc: "Catalog publishing" },
]

export function AdminDashboard() {
  const navigate = useNavigate()
  const { toast } = useToast()
  const [stats, setStats] = useState<AdminDashboardStats | null>(null)
  const [dailyBudgets, setDailyBudgets] = useState<AdminDailyApiBudget[]>([])
  const [logs, setLogs] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [scanning, setScanning] = useState(false)
  const [loadError, setLoadError] = useState<string | null>(null)

  const isApp = window.location.pathname.startsWith("/app")
  const prefix = isApp ? "/app" : ""

  const loadDashboard = async () => {
    setLoading(true)
    setLoadError(null)
    const [statsRes, budgetsRes, logsRes] = await Promise.allSettled([
      adminApi.stats(),
      adminApi.dailyBudgets(),
      adminApi.logs({ limit: 6 }),
    ])

    const errors: string[] = []
    if (statsRes.status === "fulfilled") {
      setStats(statsRes.value)
    } else {
      setStats(null)
      errors.push("Overview statistics could not be loaded.")
    }

    if (budgetsRes.status === "fulfilled" && Array.isArray(budgetsRes.value.daily_limits)) {
      setDailyBudgets(budgetsRes.value.daily_limits)
    } else {
      setDailyBudgets([])
      errors.push("Daily API budgets could not be loaded.")
    }

    if (logsRes.status === "fulfilled" && Array.isArray(logsRes.value?.logs)) {
      setLogs(logsRes.value.logs)
    } else {
      setLogs([])
      errors.push("Recent activity could not be loaded.")
    }

    setLoadError(errors.length > 0 ? errors.join(" ") : null)
    setLoading(false)
  }

  useEffect(() => {
    loadDashboard()
  }, [])

  const handleTriggerScan = async () => {
    setScanning(true)
    try {
      await adminApi.triggerRun()
      toast({
        title: "Autonomous Scan Triggered",
        description: "Collectors started pipeline execution across configured sources.",
        variant: "success",
      })
      setTimeout(loadDashboard, 2000)
    } catch (err: any) {
      toast({
        title: "Scan Trigger Failed",
        description: err.message || "Failed to trigger scan.",
        variant: "destructive",
      })
    } finally {
      setScanning(false)
    }
  }

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 border-b pb-4">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-2xl font-bold tracking-tight text-foreground">
              Admin Overview
            </h2>
            <Badge variant="outline" className="text-xs font-normal text-primary border-primary/20 bg-primary/5">
              Admin console
            </Badge>
          </div>
          <p className="text-sm text-muted-foreground mt-1">
            Pipeline orchestration, candidate verification telemetry, and administrative controls.
          </p>
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2.5 flex-wrap">
          <Button
            size="sm"
            onClick={handleTriggerScan}
            disabled={scanning}
            className="bg-cyber-blue hover:bg-cyber-blue-light text-white text-xs shadow-sm"
          >
            <Play className={`h-3.5 w-3.5 mr-1.5 ${scanning ? "animate-spin" : ""}`} />
            {scanning ? "Triggering Scan..." : "Run Pipeline Scan"}
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={loadDashboard}
            className="text-xs"
          >
            <RotateCw className="h-3.5 w-3.5 mr-1.5" /> Refresh
          </Button>
        </div>
      </div>

      {loadError && (
        <div role="alert" className="rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
          {loadError}
        </div>
      )}

      {/* KPI Metrics */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="border border-border shadow-sm">
          <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
            <CardTitle className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              Production Opportunities
            </CardTitle>
            <ShieldCheck className="h-4 w-4 text-cyber-blue" />
          </CardHeader>
          <CardContent>
            {loading ? <Skeleton className="h-8 w-16" /> : (
              <div className="text-2xl font-bold text-foreground">
                {stats?.total_production ?? "—"}
              </div>
            )}
            <p className="text-xs text-muted-foreground mt-1">
              Active and published in catalog
            </p>
          </CardContent>
        </Card>

        <Card className="border border-border shadow-sm">
          <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
            <CardTitle className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              Candidates Staged
            </CardTitle>
            <Layers className="h-4 w-4 text-indigo-500" />
          </CardHeader>
          <CardContent>
            {loading ? <Skeleton className="h-8 w-16" /> : (
              <div className="text-2xl font-bold text-foreground">
                {stats?.total_discovered ?? "—"}
              </div>
            )}
            <p className="text-xs text-muted-foreground mt-1">
              DiscoveredCandidates pipeline
            </p>
          </CardContent>
        </Card>

        <Card className="border border-border shadow-sm">
          <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
            <CardTitle className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              Free Verified
            </CardTitle>
            <CheckCircle2 className="h-4 w-4 text-emerald-600" />
          </CardHeader>
          <CardContent>
            {loading ? <Skeleton className="h-8 w-16" /> : (
              <div className="text-2xl font-bold text-emerald-600">
                {stats?.total_approved ?? "—"}
              </div>
            )}
            <p className="text-xs text-muted-foreground mt-1">
              100% Free-to-apply confirmed
            </p>
          </CardContent>
        </Card>

        <Card className="border border-border shadow-sm">
          <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
            <CardTitle className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              Quarantine Review
            </CardTitle>
            <AlertTriangle className="h-4 w-4 text-amber-500" />
          </CardHeader>
          <CardContent>
            {loading ? <Skeleton className="h-8 w-16" /> : (
              <div className="text-2xl font-bold text-amber-600">
                {stats?.total_quarantined ?? "—"}
              </div>
            )}
            <p className="text-xs text-muted-foreground mt-1">
              Ambiguous pricing flagged
            </p>
          </CardContent>
        </Card>
      </div>

      <Card className="border border-border shadow-sm">
        <CardHeader className="pb-3 border-b">
          <CardTitle className="text-sm font-semibold flex items-center gap-2">
            <Gauge className="h-4 w-4 text-cyber-blue" /> Daily API budgets
          </CardTitle>
          <p className="text-xs text-muted-foreground">
            Application-configured request limits, not provider account credit balances.
          </p>
        </CardHeader>
        <CardContent className="pt-4">
          {loading ? (
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {[1, 2, 3].map((item) => <Skeleton key={item} className="h-20 w-full" />)}
            </div>
          ) : dailyBudgets.length === 0 ? (
            <p className="text-sm text-muted-foreground">Daily API budgets are unavailable.</p>
          ) : (
            <>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                {dailyBudgets.map((budget) => (
                  <div key={budget.provider} className="rounded-lg border bg-muted/20 p-3">
                    <p className="text-xs font-semibold text-foreground">{budget.provider}</p>
                    <p className="mt-1 text-xl font-bold text-foreground">
                      {budget.daily_limit.toLocaleString()} <span className="text-xs font-medium text-muted-foreground">{budget.unit}/day</span>
                    </p>
                    <p className="mt-1 text-[11px] text-muted-foreground">{budget.operation}</p>
                  </div>
                ))}
              </div>
              <p className="mt-3 text-[11px] text-muted-foreground">
                Provider credit usage and remaining balances are not currently reported; these are app budget settings.
              </p>
            </>
          )}
        </CardContent>
      </Card>

      {/* Pipeline Stages Strip */}
      <Card className="border border-border shadow-sm">
        <CardHeader className="pb-3 border-b">
          <CardTitle className="text-sm font-semibold flex items-center justify-between">
            <span className="flex items-center gap-2">
              <Layers className="h-4 w-4 text-cyber-blue" /> Pipeline workflow
            </span>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigate(`${prefix}/admin/scheduler`)}
              className="text-xs text-muted-foreground hover:text-foreground h-7"
            >
              Scheduler Details <ArrowRight className="h-3 w-3 ml-1" />
            </Button>
          </CardTitle>
        </CardHeader>
        <CardContent className="pt-4">
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
            {pipelineStages.map((stg, idx) => (
              <div
                key={idx}
                className="p-3 rounded-lg border bg-muted/20 space-y-1 relative"
              >
                <div className="flex items-center justify-between text-[11px] font-mono text-muted-foreground">
                  <span>0{idx + 1}</span>
                  <span className="text-[9px] uppercase tracking-wider">Stage</span>
                </div>
                <h4 className="text-xs font-semibold text-foreground truncate">{stg.name}</h4>
                <p className="text-[10px] text-muted-foreground truncate">{stg.desc}</p>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      {/* Grid: Subsystems Navigation & Recent Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Operations Quick Nav (1 Col) */}
        <div className="space-y-4">
          <h3 className="text-sm font-semibold tracking-tight text-foreground uppercase tracking-wider">
            Admin Subsystems
          </h3>
          <div className="space-y-2.5">
            <div
              onClick={() => navigate(`${prefix}/admin/collectors`)}
              className="p-3.5 rounded-lg border bg-card hover:border-cyber-blue/50 cursor-pointer transition-all flex items-center justify-between shadow-sm"
            >
              <div className="flex items-center gap-3">
                <div className="h-9 w-9 rounded-lg bg-cyber-blue/10 text-cyber-blue flex items-center justify-center shrink-0">
                  <Cpu className="h-4 w-4" />
                </div>
                <div>
                  <h4 className="text-xs font-semibold text-foreground">AI Discovery Collectors</h4>
                  <p className="text-[10px] text-muted-foreground">Tavily, Firecrawl, Groq, Gemini</p>
                </div>
              </div>
              <ArrowRight className="h-4 w-4 text-muted-foreground" />
            </div>

            <div
              onClick={() => navigate(`${prefix}/admin/data-quality`)}
              className="p-3.5 rounded-lg border bg-card hover:border-amber-500/50 cursor-pointer transition-all flex items-center justify-between shadow-sm"
            >
              <div className="flex items-center gap-3">
                <div className="h-9 w-9 rounded-lg bg-amber-500/10 text-amber-500 flex items-center justify-center shrink-0">
                  <AlertTriangle className="h-4 w-4" />
                </div>
                <div>
                  <h4 className="text-xs font-semibold text-foreground">Data Quality &amp; Quarantine</h4>
                  <p className="text-[10px] text-muted-foreground">Review flagged candidates</p>
                </div>
              </div>
              <ArrowRight className="h-4 w-4 text-muted-foreground" />
            </div>

            <div
              onClick={() => navigate(`${prefix}/admin/analytics`)}
              className="p-3.5 rounded-lg border bg-card hover:border-purple-500/50 cursor-pointer transition-all flex items-center justify-between shadow-sm"
            >
              <div className="flex items-center gap-3">
                <div className="h-9 w-9 rounded-lg bg-purple-500/10 text-purple-600 flex items-center justify-center shrink-0">
                  <Activity className="h-4 w-4" />
                </div>
                <div>
                  <h4 className="text-xs font-semibold text-foreground">Discovery Analytics</h4>
                  <p className="text-[10px] text-muted-foreground">Trends, distributions, benchmarks</p>
                </div>
              </div>
              <ArrowRight className="h-4 w-4 text-muted-foreground" />
            </div>

            <div
              onClick={() => navigate(`${prefix}/admin/users`)}
              className="p-3.5 rounded-lg border bg-card hover:border-emerald-500/50 cursor-pointer transition-all flex items-center justify-between shadow-sm"
            >
              <div className="flex items-center gap-3">
                <div className="h-9 w-9 rounded-lg bg-emerald-500/10 text-emerald-600 flex items-center justify-center shrink-0">
                  <Users className="h-4 w-4" />
                </div>
                <div>
                  <h4 className="text-xs font-semibold text-foreground">User &amp; RBAC Access</h4>
                  <p className="text-[10px] text-muted-foreground">Roles, status locks, provisioning</p>
                </div>
              </div>
              <ArrowRight className="h-4 w-4 text-muted-foreground" />
            </div>
          </div>
        </div>

        {/* Right: Recent Activity Table (2 Cols) */}
        <div className="lg:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold tracking-tight text-foreground uppercase tracking-wider flex items-center gap-2">
              <Activity className="h-4 w-4 text-cyber-blue" /> Recent System Activity
            </h3>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigate(`${prefix}/admin/logs`)}
              className="text-xs text-muted-foreground hover:text-foreground h-7"
            >
              View Full Audit Logs <ArrowRight className="h-3 w-3 ml-1" />
            </Button>
          </div>

          <Card className="border border-border shadow-sm overflow-hidden">
            <div className="divide-y divide-border">
              {logs.length === 0 ? (
                <div className="p-8 text-center text-sm text-muted-foreground">
                  <Database className="h-8 w-8 mx-auto text-muted-foreground/40 mb-2" />
                  No recent activity is available.
                </div>
              ) : (
                logs.map((log, lIdx) => (
                  <div key={lIdx} className="p-3.5 flex items-start justify-between gap-4 text-xs hover:bg-muted/30 transition-colors">
                    <div className="space-y-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-foreground truncate">
                          {log.module || "SYSTEM"}
                        </span>
                        <span
                          className={`px-1.5 py-0.5 rounded text-[10px] font-medium ${log.level === "ERROR" || log.level === "CRITICAL"
                              ? "bg-red-100 text-red-700 dark:bg-red-950/60 dark:text-red-300"
                              : log.level === "WARNING"
                                ? "bg-amber-100 text-amber-700 dark:bg-amber-950/60 dark:text-amber-300"
                                : "bg-muted text-muted-foreground"
                            }`}
                        >
                          {log.level || "INFO"}
                        </span>
                      </div>
                      <p className="text-muted-foreground truncate">
                        {log.message}
                      </p>
                    </div>
                    <span className="text-[11px] text-muted-foreground shrink-0 font-mono">
                      {log.created_at ? new Date(log.created_at).toLocaleTimeString() : "Time unavailable"}
                    </span>
                  </div>
                ))
              )}
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}
