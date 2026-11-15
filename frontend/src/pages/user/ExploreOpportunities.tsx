import { useState, useEffect } from "react"
import { useNavigate } from "react-router-dom"
import {
  Search,
  CheckCircle,
  Bookmark,
  ChevronLeft,
  ChevronRight,
  MapPin,
  Calendar,
  Globe,
  ExternalLink,
  SlidersHorizontal,
  AlertCircle,
} from "lucide-react"
import { opportunitiesApi } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { CategoryBadge } from "@/components/ui/badge"
import { OpportunityCardSkeleton } from "@/components/ui/skeleton"
import { EmptyState } from "@/components/ui/empty-state"
import { useToast } from "@/components/ui/toast"
import { getSafeExternalUrl } from "@/lib/utils"

const categories = [
  "All",
  "Internship",
  "Job",
  "Bug Bounty",
  "CTF",
  "Hackathon",
  "Free Course",
  "Scholarship",
  "Research",
]

export function ExploreOpportunities() {
  const navigate = useNavigate()
  const { toast } = useToast()
  const [search, setSearch] = useState("")
  const [debouncedSearch, setDebouncedSearch] = useState("")
  const [selectedCategory, setSelectedCategory] = useState("All")
  const [remoteOnly, setRemoteOnly] = useState(false)
  const [freeOnly, setFreeOnly] = useState(false)
  const [sortBy, setSortBy] = useState("recommended")
  const [page, setPage] = useState(1)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [savingIds, setSavingIds] = useState<string[]>([])
  const [reloadKey, setReloadKey] = useState(0)
  const [data, setData] = useState<{
    opportunities: any[]
    total: number
    page: number
    per_page: number
    has_next: boolean
    has_prev: boolean
  }>({
    opportunities: [],
    total: 0,
    page: 1,
    per_page: 9,
    has_next: false,
    has_prev: false,
  })

  // Debounce search
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(search)
      setPage(1)
    }, 300)
    return () => clearTimeout(timer)
  }, [search])

  useEffect(() => {
    async function fetchOpps() {
      setLoading(true)
      setError(null)
      try {
        const filters: Record<string, string | number | boolean> = {
          page,
          per_page: 9,
          sort: sortBy,
          sort_dir: sortBy === "deadline" || sortBy === "title" ? "asc" : "desc",
        }
        if (debouncedSearch) filters.q = debouncedSearch
        if (selectedCategory !== "All") filters.category = selectedCategory
        if (remoteOnly) filters.remote = true
        if (freeOnly) filters.is_free = true

        const res = await opportunitiesApi.list(filters)
        setData({
          opportunities: Array.isArray(res?.opportunities) ? res.opportunities : [],
          total: Number(res?.total) || 0,
          page: res?.page || page,
          per_page: res?.per_page || 9,
          has_next: Boolean(res?.has_next),
          has_prev: Boolean(res?.has_prev),
        })
      } catch (err) {
        setError(err instanceof Error ? err.message : "Opportunities could not be loaded.")
      } finally {
        setLoading(false)
      }
    }
    fetchOpps()
  }, [debouncedSearch, selectedCategory, remoteOnly, freeOnly, sortBy, page, reloadKey])

  const handleToggleSave = async (id: string) => {
    setSavingIds((prev) => [...prev, id])
    try {
      const result = await opportunitiesApi.toggleSave(id)
      setData((prev: any) => ({
        ...prev,
        opportunities: prev.opportunities.map((opp: any) =>
          opp.id === id ? { ...opp, is_saved: result.saved } : opp
        ),
      }))
      toast({ title: result.saved ? "Opportunity saved" : "Bookmark removed", variant: "success" })
    } catch (err) {
      toast({
        title: "Bookmark update failed",
        description: err instanceof Error ? err.message : "Please try again.",
        variant: "destructive",
      })
    } finally {
      setSavingIds((prev) => prev.filter((itemId) => itemId !== id))
    }
  }

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.16em] text-cyber-blue">Discover</p>
        <h2 className="mt-1 text-2xl font-bold tracking-tight text-foreground">Explore opportunities</h2>
        <p className="mt-1 text-sm text-muted-foreground">Find and save cybersecurity roles, programs, and learning opportunities.</p>
      </div>

      <div className="flex flex-col md:flex-row gap-4 items-stretch md:items-center justify-between">
        <div className="relative flex-1 max-w-lg">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search by keywords, skills (e.g. reverse engineering, AWS, python)..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9 bg-card shadow-sm"
            aria-label="Search opportunities"
          />
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          <div className="flex items-center gap-2 bg-card border rounded-md px-3 py-1.5 shadow-sm text-xs">
            <SlidersHorizontal className="h-3.5 w-3.5 text-muted-foreground" />
            <span className="text-muted-foreground">Sort:</span>
            <select
              value={sortBy}
              onChange={(e) => {
                setSortBy(e.target.value)
                setPage(1)
              }}
              className="bg-transparent border-none text-foreground font-medium focus:outline-none cursor-pointer"
            >
              <option value="recommended">Recommended</option>
              <option value="score">Priority Score</option>
              <option value="deadline">Deadline</option>
              <option value="newest">Recently Added</option>
              <option value="title">Alphabetical</option>
            </select>
          </div>

          <label className="flex items-center gap-2 cursor-pointer bg-card border rounded-md px-3 py-1.5 shadow-sm text-xs select-none">
            <input
              type="checkbox"
              checked={remoteOnly}
              onChange={(e) => {
                setRemoteOnly(e.target.checked)
                setPage(1)
              }}
              className="rounded border-input text-primary focus:ring-ring"
            />
            <Globe className="h-3.5 w-3.5 text-muted-foreground" />
            <span>Remote Only</span>
          </label>

          <label className="flex items-center gap-2 cursor-pointer bg-card border rounded-md px-3 py-1.5 shadow-sm text-xs select-none">
            <input
              type="checkbox"
              checked={freeOnly}
              onChange={(e) => {
                setFreeOnly(e.target.checked)
                setPage(1)
              }}
              className="rounded border-input text-emerald-600 focus:ring-emerald-500"
            />
            <CheckCircle className="h-3.5 w-3.5 text-emerald-600" />
            <span>100% Free Only</span>
          </label>
        </div>
      </div>

      <div className="flex items-center gap-2 overflow-x-auto pb-2 scrollbar-none" aria-label="Opportunity categories">
        {categories.map((cat) => (
          <button
            key={cat}
            type="button"
            aria-pressed={selectedCategory === cat}
            onClick={() => {
              setSelectedCategory(cat)
              setPage(1)
            }}
            className={`whitespace-nowrap px-3 py-1 rounded-full text-xs font-medium transition-all ${
              selectedCategory === cat
                ? "bg-cyber-blue text-white shadow-sm"
                : "bg-card border text-muted-foreground hover:border-cyber-blue hover:text-foreground"
            }`}
          >
            {cat}
          </button>
        ))}
      </div>

      <div className="flex items-center justify-between text-sm text-muted-foreground border-b pb-3">
        <span>
          {loading ? "Loading opportunities…" : `${data.total} ${data.total === 1 ? "opportunity" : "opportunities"}`}
        </span>
        {data.total > 0 && <span>Page {data.page} of {Math.ceil(data.total / data.per_page)}</span>}
      </div>

      {error && (
        <div role="alert" className="flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
          <Button variant="outline" size="sm" className="ml-auto" onClick={() => setReloadKey((key) => key + 1)}>Retry</Button>
        </div>
      )}

      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {Array.from({ length: 6 }).map((_, i) => (
            <OpportunityCardSkeleton key={i} />
          ))}
        </div>
      ) : error ? null : data.opportunities.length === 0 ? (
        <EmptyState
          title="No cybersecurity opportunities found"
          description="Try a different search or adjust your filters."
          actionLabel="Reset Filters"
          onAction={() => {
            setSearch("")
            setSelectedCategory("All")
            setRemoteOnly(false)
            setFreeOnly(false)
          }}
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {data.opportunities.map((opp: any) => {
            const sourceUrl = getSafeExternalUrl(opp.url || opp.source_url)
            return (
            <article
              key={opp.id}
              className="group rounded-xl border bg-card p-5 shadow-sm hover:border-cyber-blue/50 hover:shadow-md transition-all flex flex-col justify-between space-y-4"
            >
              <div className="space-y-3">
                <div className="flex items-center justify-between gap-2">
                  <CategoryBadge category={opp.category} />
                  <div className="flex items-center gap-1.5">
                    <span className={`inline-flex items-center gap-1 rounded px-2 py-0.5 text-[10px] font-semibold border ${
                      opp.is_free === true ? "bg-emerald-500/10 text-emerald-700 border-emerald-500/20" :
                        opp.is_free === false ? "bg-muted text-muted-foreground border-border" : "bg-muted text-muted-foreground border-border"
                    }`}>
                      {opp.is_free === true && <CheckCircle className="h-3 w-3" />}
                      {opp.is_free === true ? "Free" : opp.is_free === false ? "Paid" : "Fee not listed"}
                    </span>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => void handleToggleSave(opp.id)}
                      disabled={savingIds.includes(opp.id)}
                      aria-label={`${opp.is_saved ? "Remove bookmark for" : "Save"} ${opp.title || "opportunity"}`}
                      className="h-7 w-7 text-muted-foreground hover:text-purple-600"
                    >
                      <Bookmark className={`h-4 w-4 ${opp.is_saved ? "fill-purple-600 text-purple-600" : ""}`} />
                    </Button>
                  </div>
                </div>

                <button
                  type="button"
                  onClick={() => navigate(`/app/opportunities/${opp.id}`)}
                  className="block w-full text-left rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <h3 className="font-semibold text-base text-foreground group-hover:text-cyber-blue transition-colors line-clamp-2">
                    {opp.title}
                  </h3>
                  <p className="text-xs text-muted-foreground font-medium mt-1">
                    {opp.company || opp.provider || opp.organization || "Organization not listed"}
                  </p>
                  {(opp.description || opp.description_snippet) && (
                    <p className="text-xs text-muted-foreground line-clamp-2 leading-relaxed mt-3">
                      {opp.description || opp.description_snippet}
                    </p>
                  )}
                </button>

                {/* Tags / Skills Required */}
                {Array.isArray(opp.tags) && opp.tags.length > 0 && (
                  <div className="flex flex-wrap gap-1.5 pt-1">
                    {opp.tags.slice(0, 3).map((skill: string, sIdx: number) => (
                      <span
                        key={sIdx}
                        className="text-[10px] font-mono px-2 py-0.5 rounded bg-muted text-muted-foreground"
                      >
                        {skill}
                      </span>
                    ))}
                    {opp.tags.length > 3 && (
                      <span className="text-[10px] font-mono text-muted-foreground self-center">
                        +{opp.tags.length - 3}
                      </span>
                    )}
                  </div>
                )}
              </div>

              {/* Card Footer: Metadata + Score Bar */}
              <div className="border-t pt-3 space-y-2.5">
                <div className="flex items-center justify-between text-xs text-muted-foreground">
                  <div className="flex items-center gap-1 truncate max-w-[150px]">
                    <MapPin className="h-3 w-3 shrink-0" />
                    <span className="truncate">{opp.location || (opp.remote ? "Remote" : "Location not listed")}</span>
                  </div>
                  {opp.deadline && (
                    <div className="flex items-center gap-1 shrink-0 font-medium text-amber-600 dark:text-amber-400">
                      <Calendar className="h-3 w-3" />
                      <span>{new Date(opp.deadline).toLocaleDateString()}</span>
                    </div>
                  )}
                </div>

                {(opp.score ?? opp.priority_score) != null && (
                  <div className="space-y-1">
                    <div className="flex justify-between text-[10px] font-mono text-muted-foreground">
                      <span>Priority score</span>
                      <span>{Math.round(opp.score ?? opp.priority_score)}/100</span>
                    </div>
                    <div className="h-1.5 w-full bg-muted rounded-full overflow-hidden">
                      <div
                        className="h-full bg-cyber-blue rounded-full"
                        style={{ width: `${Math.min(100, Math.max(0, Number(opp.score ?? opp.priority_score))) }%` }}
                      />
                    </div>
                  </div>
                )}

                {sourceUrl && (
                  <a
                    href={sourceUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    aria-label={`Open the original listing for ${opp.title} in a new tab`}
                    className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-primary/25 bg-primary/10 px-3 py-2 text-xs font-semibold text-primary transition-colors hover:bg-primary hover:text-primary-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    View original listing <ExternalLink className="h-3.5 w-3.5" />
                  </a>
                )}
              </div>
            </article>
            )
          })}
        </div>
      )}

      {data.total > (data.per_page || 9) && (
        <div className="flex items-center justify-center gap-3 pt-4 border-t">
          <Button
            variant="outline"
            size="sm"
            disabled={!data.has_prev}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
            className="text-xs"
          >
            <ChevronLeft className="h-4 w-4 mr-1" /> Previous
          </Button>
          <span className="text-xs text-muted-foreground font-mono">
            Page {page} of {Math.ceil(data.total / (data.per_page || 9))}
          </span>
          <Button
            variant="outline"
            size="sm"
            disabled={!data.has_next}
            onClick={() => setPage((p) => p + 1)}
            className="text-xs"
          >
            Next <ChevronRight className="h-4 w-4 ml-1" />
          </Button>
        </div>
      )}
    </div>
  )
}

