import { useEffect, useState } from "react"
import { useNavigate } from "react-router-dom"
import {
  Compass,
  Sparkles,
  Bookmark,
  Clock,
  ArrowRight,
  ShieldCheck,
  CheckCircle,
} from "lucide-react"
import { useAuth } from "@/lib/auth-context"
import { opportunitiesApi, dashboardApi } from "@/lib/api"
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { CategoryBadge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"

export function UserDashboard() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [stats, setStats] = useState<any>(null)
  const [recentOpps, setRecentOpps] = useState<any[]>([])
  const [savedOpps, setSavedOpps] = useState<any[]>([])
  const [savedCount, setSavedCount] = useState<number | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    async function loadData() {
      try {
        const [statsRes, oppsRes, savedRes] = await Promise.allSettled([
          dashboardApi.stats(),
          opportunitiesApi.list({ per_page: 5 }),
          opportunitiesApi.saved(),
        ])

        if (statsRes.status === "fulfilled") setStats(statsRes.value)
        if (oppsRes.status === "fulfilled" && oppsRes.value?.opportunities) {
          setRecentOpps(oppsRes.value.opportunities)
        }
        if (savedRes.status === "fulfilled" && savedRes.value?.opportunities) {
          setSavedOpps(savedRes.value.opportunities.slice(0, 4))
          setSavedCount(savedRes.value.total ?? savedRes.value.opportunities.length)
        }
      } catch (e) {
        console.error("Dashboard data load error", e)
      } finally {
        setLoading(false)
      }
    }
    loadData()
  }, [])

  const handleToggleSave = async (id: string, e: React.MouseEvent) => {
    e.stopPropagation()
    try {
      await opportunitiesApi.toggleSave(id)
      setRecentOpps((prev) =>
        prev.map((opp) =>
          opp.id === id ? { ...opp, is_saved: !opp.is_saved } : opp
        )
      )
      const current = recentOpps.find((opp) => opp.id === id)
      if (current) {
        setSavedCount((count) => count === null ? null : count + (current.is_saved ? -1 : 1))
      }
    } catch (err) {
      console.error(err)
    }
  }

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      {/* Welcome Banner */}
      <div className="rounded-xl bg-gradient-to-r from-cyber-blue/10 via-primary/5 to-card border p-6 shadow-sm">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="inline-flex items-center gap-2 px-2.5 py-1 rounded-full bg-cyber-blue/15 text-cyber-blue text-xs font-medium mb-3">
              <ShieldCheck className="h-3.5 w-3.5" /> Cybersecurity opportunity discovery
            </div>
            <h2 className="text-2xl md:text-3xl font-bold tracking-tight text-foreground">
              Welcome back, {user?.username || "Researcher"}
            </h2>
            <p className="text-sm text-muted-foreground mt-1 max-w-xl">
              Real-time autonomous discovery of cybersecurity internships, bug bounties, CTFs, scholarships, and research grants.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <Button
              onClick={() => navigate("/app/opportunities")}
              className="bg-cyber-blue hover:bg-cyber-blue-light text-white shadow-sm"
            >
              Explore Feed <ArrowRight className="ml-2 h-4 w-4" />
            </Button>
          </div>
        </div>
      </div>

      {/* 4 KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card className="border-l-4 border-l-cyber-blue">
          <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
            <CardTitle className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              Total Opportunities
            </CardTitle>
            <Compass className="h-4 w-4 text-cyber-blue" />
          </CardHeader>
          <CardContent>
            {loading ? (
              <Skeleton className="h-8 w-16" />
            ) : (
              <div className="text-2xl font-bold text-foreground">
                {stats?.total_opportunities ?? stats?.total ?? "—"}
              </div>
            )}
            <p className="text-xs text-muted-foreground mt-1">Verified active listings</p>
          </CardContent>
        </Card>

        <Card className="border-l-4 border-l-emerald-500">
          <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
            <CardTitle className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              New This Week
            </CardTitle>
            <Sparkles className="h-4 w-4 text-emerald-500" />
          </CardHeader>
          <CardContent>
            {loading ? (
              <Skeleton className="h-8 w-16" />
            ) : (
              <div className="text-2xl font-bold text-foreground">
                {stats?.new_this_week ?? "—"}
              </div>
            )}
            <p className="text-xs text-muted-foreground mt-1">Discovered by AI collectors</p>
          </CardContent>
        </Card>

        <Card className="border-l-4 border-l-purple-500">
          <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
            <CardTitle className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              Saved
            </CardTitle>
            <Bookmark className="h-4 w-4 text-purple-500" />
          </CardHeader>
          <CardContent>
            {loading ? (
              <Skeleton className="h-8 w-16" />
            ) : (
              <div className="text-2xl font-bold text-foreground">
                {savedCount ?? stats?.saved_count ?? "—"}
              </div>
            )}
            <p className="text-xs text-muted-foreground mt-1">Bookmarked for application</p>
          </CardContent>
        </Card>

        <Card className="border-l-4 border-l-amber-500">
          <CardHeader className="flex flex-row items-center justify-between pb-2 space-y-0">
            <CardTitle className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
              Closing Soon
            </CardTitle>
            <Clock className="h-4 w-4 text-amber-500" />
          </CardHeader>
          <CardContent>
            {loading ? (
              <Skeleton className="h-8 w-16" />
            ) : (
              <div className="text-2xl font-bold text-foreground">
                {stats?.expiring_soon ?? "—"}
              </div>
            )}
            <p className="text-xs text-muted-foreground mt-1">Deadlines in &lt; 7 days</p>
          </CardContent>
        </Card>
      </div>

      {/* Main Grid: Recently Discovered & Saved Quick Access */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Recently Discovered (2 Cols) */}
        <div className="lg:col-span-2 space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold tracking-tight text-foreground flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-cyber-blue" /> Recently Discovered
            </h3>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigate("/app/opportunities")}
              className="text-xs text-muted-foreground hover:text-foreground"
            >
              View all
            </Button>
          </div>

          {loading ? (
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <div key={i} className="p-4 rounded-lg border bg-card space-y-2">
                  <Skeleton className="h-5 w-1/3" />
                  <Skeleton className="h-4 w-full" />
                </div>
              ))}
            </div>
          ) : recentOpps.length === 0 ? (
            <Card className="p-8 text-center border-dashed">
              <p className="text-sm text-muted-foreground">No recent opportunities yet.</p>
            </Card>
          ) : (
            <div className="space-y-3">
              {recentOpps.map((opp) => (
                <div
                  key={opp.id}
                  onClick={() => navigate(`/app/opportunities/${opp.id}`)}
                  className="group relative p-4 rounded-lg border bg-card hover:border-cyber-blue/40 hover:shadow-md transition-all cursor-pointer flex flex-col sm:flex-row sm:items-center justify-between gap-3"
                >
                  <div className="space-y-1.5 flex-1 pr-4">
                    <div className="flex items-center gap-2 flex-wrap">
                      <CategoryBadge category={opp.category} />
                      {opp.is_free === true && (
                        <span className="inline-flex items-center gap-1 rounded bg-emerald-500/10 px-2 py-0.5 text-[11px] font-medium text-emerald-600 dark:text-emerald-400">
                          <CheckCircle className="h-3 w-3" /> Free
                        </span>
                      )}
                      {(opp.score ?? opp.priority_score) != null && (
                        <span className="text-[11px] font-mono text-muted-foreground">
                          Score: {Math.round(opp.score ?? opp.priority_score)}
                        </span>
                      )}
                    </div>
                    <h4 className="text-sm font-semibold text-foreground group-hover:text-cyber-blue transition-colors line-clamp-1">
                      {opp.title}
                    </h4>
                    <p className="text-xs text-muted-foreground line-clamp-1">
                      {opp.company || opp.provider || opp.organization || "Organization not listed"} • {opp.location || (opp.remote ? "Remote" : "Location not listed")}
                    </p>
                  </div>

                  <div className="flex items-center gap-2 self-end sm:self-center">
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={(e) => handleToggleSave(opp.id, e)}
                      className="h-8 w-8 text-muted-foreground hover:text-purple-600"
                      title={opp.is_saved ? "Remove bookmark" : "Save opportunity"}
                    >
                      <Bookmark className={`h-4 w-4 ${opp.is_saved ? "fill-purple-600 text-purple-600" : ""}`} />
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      className="text-xs h-8"
                      onClick={(e) => {
                        e.stopPropagation()
                        navigate(`/app/opportunities/${opp.id}`)
                      }}
                    >
                      Details
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Right: Saved Quick Access (1 Col) */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-semibold tracking-tight text-foreground flex items-center gap-2">
              <Bookmark className="h-4 w-4 text-purple-500" /> Bookmarked
            </h3>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => navigate("/app/saved")}
              className="text-xs text-muted-foreground hover:text-foreground"
            >
              View all
            </Button>
          </div>

          {loading ? (
            <div className="space-y-3">
              {[1, 2].map((i) => (
                <div key={i} className="p-4 rounded-lg border bg-card space-y-2">
                  <Skeleton className="h-4 w-1/2" />
                  <Skeleton className="h-3 w-3/4" />
                </div>
              ))}
            </div>
          ) : savedOpps.length === 0 ? (
            <Card className="p-6 text-center border-dashed">
              <Bookmark className="h-8 w-8 text-muted-foreground mx-auto mb-2 opacity-40" />
              <p className="text-xs text-muted-foreground">
                No bookmarked opportunities yet. Click the bookmark icon on any opportunity to save it here.
              </p>
            </Card>
          ) : (
            <div className="space-y-3">
              {savedOpps.map((opp) => (
                <div
                  key={opp.id}
                  onClick={() => navigate(`/app/opportunities/${opp.id}`)}
                  className="p-3.5 rounded-lg border bg-card hover:border-purple-500/40 transition-colors cursor-pointer space-y-1"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] font-semibold uppercase tracking-wider text-purple-600">
                      {opp.category || "Opportunity"}
                    </span>
                    {opp.deadline && (
                      <span className="text-[10px] text-muted-foreground">
                        {new Date(opp.deadline).toLocaleDateString()}
                      </span>
                    )}
                  </div>
                  <h5 className="text-xs font-medium text-foreground line-clamp-1 hover:text-purple-600">
                    {opp.title}
                  </h5>
                  <p className="text-[11px] text-muted-foreground line-clamp-1">
                    {opp.organization || opp.company || opp.provider || "Organization not listed"}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

