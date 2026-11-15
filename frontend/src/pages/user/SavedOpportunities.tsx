import { useEffect, useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import { Bookmark, Search, Trash2, Calendar, MapPin, AlertCircle, ExternalLink } from "lucide-react"
import { opportunitiesApi } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { CategoryBadge } from "@/components/ui/badge"
import { OpportunityCardSkeleton } from "@/components/ui/skeleton"
import { EmptyState } from "@/components/ui/empty-state"
import { useToast } from "@/components/ui/toast"
import { getSafeExternalUrl } from "@/lib/utils"

export function SavedOpportunities() {
  const navigate = useNavigate()
  const { toast } = useToast()
  const [savedList, setSavedList] = useState<any[]>([])
  const [search, setSearch] = useState("")
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [removingIds, setRemovingIds] = useState<string[]>([])

  const loadSaved = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await opportunitiesApi.saved()
      setSavedList(Array.isArray(res?.opportunities) ? res.opportunities : [])
    } catch (err) {
      setError(err instanceof Error ? err.message : "Saved opportunities could not be loaded.")
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void loadSaved()
  }, [])

  const handleRemove = async (id: string) => {
    setRemovingIds((prev) => [...prev, id])
    try {
      await opportunitiesApi.toggleSave(id)
      setSavedList((prev) => prev.filter((opp) => opp.id !== id))
      toast({ title: "Bookmark removed", variant: "success" })
    } catch (err) {
      toast({
        title: "Could not remove bookmark",
        description: err instanceof Error ? err.message : "Please try again.",
        variant: "destructive",
      })
    } finally {
      setRemovingIds((prev) => prev.filter((itemId) => itemId !== id))
    }
  }

  const filtered = savedList.filter((opp) => {
    if (!search) return true
    const q = search.toLowerCase()
    return (
      opp.title?.toLowerCase().includes(q) ||
      opp.organization?.toLowerCase().includes(q) ||
      opp.category?.toLowerCase().includes(q)
    )
  })

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-cyber-blue">Your workspace</p>
          <h2 className="mt-1 text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
            <Bookmark className="h-6 w-6 text-cyber-blue" /> Saved opportunities
          </h2>
          <p className="text-sm text-muted-foreground mt-1">
            Keep the listings you want to revisit in one place.
          </p>
        </div>

        <div className="relative w-full sm:w-72">
          <Search className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search saved..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9 bg-card"
            aria-label="Search saved opportunities"
          />
        </div>
      </div>

      {error && (
        <div role="alert" className="flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/5 p-3 text-sm text-destructive">
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
          <Button variant="outline" size="sm" className="ml-auto" onClick={() => void loadSaved()}>Retry</Button>
        </div>
      )}

      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {Array.from({ length: 3 }).map((_, i) => (
            <OpportunityCardSkeleton key={i} />
          ))}
        </div>
      ) : error ? null : filtered.length === 0 && savedList.length === 0 ? (
        <EmptyState
          icon={Bookmark}
          title="No bookmarked opportunities"
          description="Save a listing from the opportunity feed and it will appear here."
          actionLabel="Explore Opportunities"
          onAction={() => navigate("/app/opportunities")}
        />
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={Search}
          title="No matches"
          description="No saved listings match this search."
          actionLabel="Clear search"
          onAction={() => setSearch("")}
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {filtered.map((opp) => {
            const sourceUrl = getSafeExternalUrl(opp.url || opp.source_url)
            return (
            <article
              key={opp.id}
              className="group rounded-xl border bg-card p-5 shadow-sm hover:border-cyber-blue/40 hover:shadow-md transition-all flex flex-col justify-between space-y-4"
            >
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <CategoryBadge category={opp.category} />
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => void handleRemove(opp.id)}
                    disabled={removingIds.includes(opp.id)}
                    className="h-7 w-7 text-muted-foreground hover:text-destructive"
                    aria-label={`Remove ${opp.title || "opportunity"} from saved listings`}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>

                <Link to={`/app/opportunities/${opp.id}`} className="block rounded focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
                  <h3 className="font-semibold text-base text-foreground group-hover:text-cyber-blue transition-colors line-clamp-2">
                    {opp.title}
                  </h3>
                  <p className="text-xs text-muted-foreground font-medium mt-1">
                    {opp.organization || "Organization not listed"}
                  </p>
                  {opp.description && (
                    <p className="text-xs text-muted-foreground line-clamp-2 leading-relaxed mt-3">
                      {opp.description}
                    </p>
                  )}
                </Link>
              </div>

              <div className="border-t pt-3 space-y-3 text-xs text-muted-foreground">
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-1">
                    {opp.location || opp.remote ? <MapPin className="h-3 w-3 shrink-0" /> : null}
                    <span>{opp.location || (opp.remote ? "Remote" : "Location not listed")}</span>
                  </div>
                  {opp.deadline && (
                    <div className="flex items-center gap-1 font-medium text-amber-600">
                      <Calendar className="h-3 w-3" />
                      <span>{new Date(opp.deadline).toLocaleDateString()}</span>
                    </div>
                  )}
                </div>
                {sourceUrl && (
                  <a
                    href={sourceUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    aria-label={`Open the original listing for ${opp.title} in a new tab`}
                    className="inline-flex w-full items-center justify-center gap-2 rounded-lg border border-primary/25 bg-primary/10 px-3 py-2 font-semibold text-primary transition-colors hover:bg-primary hover:text-primary-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
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
    </div>
  )
}

